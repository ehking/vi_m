import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List

from django.conf import settings
from django.utils.text import slugify

logger = logging.getLogger(__name__)


@dataclass
class VideoGenerationError(Exception):
    message: str
    code: str = ""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


def _append_log(video, entries: List[str]) -> None:
    if not entries:
        return
    combined_log = "\n".join(entries)
    if video.generation_log:
        video.generation_log = f"{video.generation_log}\n{combined_log}"
    else:
        video.generation_log = combined_log


def _load_moviepy():
    """Lazy import MoviePy so tests can mock the module easily."""

    from moviepy import editor

    return editor


def generate_video_for_instance(video):
    """
    Receives a GeneratedVideo instance (or equivalent model).
    Updates its status and fields while generating a video file with MoviePy.
    Logs each major step.
    Returns the updated instance.
    """

    log_entries: List[str] = []

    def log_step(message: str) -> None:
        logger.info(message)
        log_entries.append(message)

    start_time = time.monotonic()
    log_step(f"Starting video generation for video #{video.pk}: {video.title}")

    try:
        video.status = "processing"
        video.generation_progress = 10
        video.error_message = ""
        video.error_code = ""
        video.save(update_fields=["status", "generation_progress", "error_message", "error_code"])

        audio_field = getattr(video, "audio_track", None)
        audio_file = getattr(audio_field, "audio_file", None)
        if not audio_file or not getattr(audio_file, "path", None) or not os.path.exists(audio_file.path):
            raise VideoGenerationError("Audio file is missing for this video.", code="audio_missing")

        log_step(f"Loaded audio file from {audio_file.path}")

        editor = _load_moviepy()
        AudioFileClip = getattr(editor, "AudioFileClip")
        ColorClip = getattr(editor, "ColorClip")

        audio_clip = AudioFileClip(audio_file.path)
        duration_seconds = int(audio_clip.duration or 0)
        duration_seconds = max(duration_seconds, 1)

        base_width, base_height = 1280, 720
        color_clip = ColorClip(size=(base_width, base_height), color=(10, 10, 10), duration=duration_seconds)
        color_clip = color_clip.set_audio(audio_clip)

        media_root = Path(settings.MEDIA_ROOT)
        media_root.mkdir(parents=True, exist_ok=True)
        output_dir = media_root / "videos"
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_title = slugify(video.title) or f"video-{video.pk}"
        output_path = output_dir / f"{safe_title}-{int(time.time())}.mp4"

        log_step(f"Writing video file to {output_path}")
        color_clip.write_videofile(
            output_path.as_posix(),
            fps=24,
            codec="libx264",
            audio_codec="aac",
            verbose=False,
            logger=None,
        )

        color_clip.close()
        audio_clip.close()

        relative_path = output_path.relative_to(media_root)
        video.video_file.name = relative_path.as_posix()
        video.file_size_bytes = os.path.getsize(output_path)
        video.duration_seconds = duration_seconds
        video.resolution = f"{base_width}x{base_height}"
        video.aspect_ratio = "16:9"
        video.status = "ready"
        video.generation_progress = 100
        video.generation_time_ms = int((time.monotonic() - start_time) * 1000)

        log_step("Video generation completed successfully.")
        _append_log(video, log_entries)
        video.save(
            update_fields=[
                "video_file",
                "file_size_bytes",
                "duration_seconds",
                "resolution",
                "aspect_ratio",
                "status",
                "generation_progress",
                "generation_time_ms",
                "generation_log",
            ]
        )
        return video

    except VideoGenerationError as exc:
        log_step("Generation failed: Known error encountered.")
        _append_log(video, log_entries)
        video.status = "failed"
        video.error_message = str(exc)
        video.error_code = exc.code
        video.generation_progress = 0
        video.save(
            update_fields=["status", "error_message", "error_code", "generation_progress", "generation_log"]
        )
        return video
    except Exception as exc:  # pragma: no cover - defensive catch
        logger.exception("Unexpected error during video generation")
        log_step(f"Generation failed: {exc}")
        _append_log(video, log_entries)
        video.status = "failed"
        video.error_message = str(exc)
        video.generation_progress = 0
        video.save(update_fields=["status", "error_message", "generation_progress", "generation_log"])
        return video
