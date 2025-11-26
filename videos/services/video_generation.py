import os
import traceback
import uuid
from typing import Any, Optional

from django.conf import settings
from django.core.files import File
from django.db import transaction
from django.utils import timezone

from videos.models import GeneratedVideo, VideoGenerationLog

DEFAULT_SIZE = (1280, 720)
DEFAULT_FPS = 24


def _append_text_log(video: GeneratedVideo, line: str) -> None:
    timestamp = timezone.now().isoformat()
    entry = f"[{timestamp}] {line}"
    if video.generation_log:
        video.generation_log = f"{video.generation_log}\n{entry}"
    else:
        video.generation_log = entry
    video.save(update_fields=["generation_log"])


def _log_stage(
    video: GeneratedVideo,
    stage: str,
    status: str,
    message: str = "",
    detail: str = "",
    update_error_fields: bool = False,
) -> None:
    VideoGenerationLog.objects.create(
        video=video,
        stage=stage,
        status=status,
        message=message,
        detail=detail,
    )

    update_fields = ["current_stage"]
    video.current_stage = stage
    if update_error_fields:
        now = timezone.now()
        video.error_message = message
        video.last_error_message = message
        video.last_error_at = now
        video.status = "failed"
        update_fields.extend(["error_message", "last_error_message", "last_error_at", "status"])
    video.save(update_fields=update_fields)


@transaction.atomic
def _prepare_output_path(video: GeneratedVideo) -> str:
    media_dir = os.path.join(settings.MEDIA_ROOT, "videos")
    os.makedirs(media_dir, exist_ok=True)
    filename = f"generated_{video.pk or 'video'}_{uuid.uuid4().hex}.mp4"
    return os.path.join(media_dir, filename), filename


def generate_video_for_instance(video: GeneratedVideo) -> GeneratedVideo:
    try:
        from moviepy.editor import AudioFileClip, ColorClip
    except ImportError as exc:  # pragma: no cover - dependency edge
        raise ImportError(
            "moviepy is required for video generation. Install it via requirements.txt"
        ) from exc

    start_ts = timezone.now()
    _log_stage(video, "start", "started", "Generation triggered")
    video.status = "processing"
    video.generation_progress = 5
    video.error_message = ""
    video.last_error_message = ""
    video.last_error_at = None
    video.save(
        update_fields=[
            "status",
            "generation_progress",
            "error_message",
            "last_error_message",
            "last_error_at",
        ]
    )

    audio_clip: Optional[Any] = None
    video_clip = None

    try:
        _log_stage(video, "load_audio", "started", "Loading audio track")
        if not video.audio_track or not video.audio_track.audio_file:
            raise ValueError("No audio track attached to this video")
        if not hasattr(video.audio_track.audio_file, "path"):
            raise ValueError("Audio file path is unavailable")

        audio_path = video.audio_track.audio_file.path
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration or 0
        _log_stage(
            video,
            "load_audio",
            "success",
            f"Loaded audio ({duration:.2f}s)",
        )

        _log_stage(video, "prepare_video", "started", "Preparing video canvas")
        base_clip = ColorClip(size=DEFAULT_SIZE, color=(20, 20, 20)).set_duration(max(duration, 1))
        _log_stage(video, "prepare_video", "success", "Base clip ready")

        _log_stage(video, "attach_audio", "started", "Attaching audio to clip")
        video_clip = base_clip.set_audio(audio_clip)
        _log_stage(video, "attach_audio", "success", "Audio attached")

        _log_stage(video, "write_file", "started", "Rendering video to file")
        output_path, filename = _prepare_output_path(video)
        video_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=DEFAULT_FPS,
            verbose=False,
            logger=None,
        )
        _log_stage(video, "write_file", "success", f"File written to {output_path}")

        with open(output_path, "rb") as fp:
            video.video_file.save(filename, File(fp), save=False)

        video.duration_seconds = int(duration)
        video.resolution = f"{DEFAULT_SIZE[0]}x{DEFAULT_SIZE[1]}"
        video.aspect_ratio = "16:9"
        video.file_size_bytes = os.path.getsize(output_path)
        video.generation_progress = 100
        video.status = "ready"
        video.generation_time_ms = int((timezone.now() - start_ts).total_seconds() * 1000)
        video.current_stage = "finalize"
        video.save(
            update_fields=[
                "video_file",
                "duration_seconds",
                "resolution",
                "aspect_ratio",
                "file_size_bytes",
                "generation_progress",
                "status",
                "generation_time_ms",
                "current_stage",
            ]
        )
        _append_text_log(video, "Video generated successfully")
        _log_stage(video, "finalize", "success", "Generation complete")
        return video
    except Exception as exc:  # noqa: BLE001
        detail = traceback.format_exc()
        _append_text_log(video, f"Generation failed: {exc}")
        _log_stage(
            video,
            video.current_stage or "unknown",
            "failed",
            str(exc),
            detail=detail,
            update_error_fields=True,
        )
        raise
    finally:
        if audio_clip:
            audio_clip.close()
        if video_clip:
            video_clip.close()
