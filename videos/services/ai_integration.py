import json
import logging
import os
from typing import Any, Dict

import requests
from django.conf import settings
from django.core.files import File
from django.db import transaction

from videos.models import AIProviderConfig, AIVideoJob, GeneratedVideo

logger = logging.getLogger(__name__)


def _parse_json_field(raw_value: str) -> Dict[str, Any]:
    if not raw_value:
        return {}
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        logger.warning("Failed to parse JSON field: %s", raw_value)
        return {}


def _build_headers(provider: AIProviderConfig) -> Dict[str, str]:
    headers: Dict[str, str] = {
        "Accept": "application/json",
    }
    if provider.api_key:
        headers["Authorization"] = f"Bearer {provider.api_key}"

    extra_headers = _parse_json_field(provider.extra_headers)
    headers.update({str(k): str(v) for k, v in extra_headers.items()})
    return headers


def _build_payload(job: AIVideoJob) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "prompt": job.prompt,
        "audio_path": job.audio_track.audio_file.path if job.audio_track and job.audio_track.audio_file else "",
    }
    if job.background_video and job.background_video.video_file:
        payload["background_video_path"] = job.background_video.video_file.path

    payload.update(_parse_json_field(job.provider.extra_payload))
    return payload


def _save_video_file(job: AIVideoJob, video_url: str) -> GeneratedVideo:
    response = requests.get(video_url, stream=True, timeout=120)
    response.raise_for_status()

    ai_dir = os.path.join(settings.MEDIA_ROOT, "ai_videos")
    os.makedirs(ai_dir, exist_ok=True)
    filename = f"ai_video_job_{job.pk}.mp4"
    filepath = os.path.join(ai_dir, filename)

    with open(filepath, "wb") as output:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                output.write(chunk)

    video_instance = job.video or GeneratedVideo(
        audio_track=job.audio_track,
        title=f"AI Video #{job.pk} - {job.provider.name}",
    )
    with open(filepath, "rb") as file_handle:
        django_file = File(file_handle)
        video_instance.video_file.save(os.path.join("ai_videos", filename), django_file, save=False)

    video_instance.status = "ready"
    video_instance.error_message = ""
    video_instance.prompt_used = job.prompt
    video_instance.save()
    return video_instance


def run_ai_video_job(job_id: int) -> AIVideoJob:
    job = (
        AIVideoJob.objects.select_related("provider", "audio_track", "background_video", "video")
        .filter(pk=job_id)
        .first()
    )
    if not job:
        raise ValueError(f"Job with id {job_id} not found")

    provider = job.provider
    if not provider.is_active:
        job.status = AIVideoJob.STATUS_FAILED
        job.error_message = "Selected provider is inactive."
        job.save(update_fields=["status", "error_message", "updated_at"])
        return job

    try:
        job.status = AIVideoJob.STATUS_RUNNING
        job.error_message = ""
        job.save(update_fields=["status", "error_message", "updated_at"])

        headers = _build_headers(provider)
        payload = _build_payload(job)
        job.request_payload = json.dumps(payload, indent=2)
        job.save(update_fields=["request_payload", "updated_at"])

        url = f"{provider.base_url.rstrip('/')}/{provider.endpoint_path.lstrip('/')}"
        logger.info("Sending AI video request to %s", url)
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        job.response_raw = response.text
        job.save(update_fields=["response_raw", "updated_at"])

        response.raise_for_status()
        data = response.json()
        video_url = data.get("video_url")
        if not video_url:
            raise ValueError("Response missing video_url field")

        with transaction.atomic():
            video_instance = _save_video_file(job, video_url)
            job.video = video_instance
            job.status = AIVideoJob.STATUS_SUCCESS
            job.error_message = ""
            job.save(update_fields=["video", "status", "error_message", "updated_at"])
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("AI video job %s failed", job_id)
        job.status = AIVideoJob.STATUS_FAILED
        job.error_message = str(exc)
        job.save(update_fields=["status", "error_message", "updated_at"])

    return job
