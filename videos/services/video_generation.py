import logging
import os
import tempfile
import time
from typing import Optional

from django.core.files import File

from ..models import GeneratedVideo

try:
    from moviepy.editor import AudioFileClip, ColorClip
except Exception:  # pragma: no cover - MoviePy import may fail in some environments
    AudioFileClip = None
    ColorClip = None


logger = logging.getLogger(__name__)


def _validate_dependencies() -> None:
    if AudioFileClip is None or ColorClip is None:
        raise ImportError("MoviePy is required for video generation but is not available.")


def _build_video_filename(video: GeneratedVideo) -> str:
    base_name = video.title.replace(" ", "_") if video.title else "video"
    return f"{base_name}_{video.pk}.mp4"


def generate_video_for_instance(video: GeneratedVideo) -> GeneratedVideo:
    """Generate a video file for the given GeneratedVideo instance.

    The function manages status updates, error handling, and persistence while producing
    a simple video from the associated audio track using MoviePy. The input instance is
    updated and saved before returning.
    """

    logger.info("Starting video generation for video %s", video.pk)
    video.status = "processing"
    video.error_message = ""
    video.save(update_fields=["status", "error_message", "updated_at"])

    start_time = time.monotonic()
    temp_path: Optional[str] = None

    try:
        _validate_dependencies()
        if not video.audio_track or not video.audio_track.audio_file:
            raise ValueError("An audio track with an uploaded file is required to generate the video.")

        audio_path = video.audio_track.audio_file.path
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found at path: {audio_path}")

        audio_clip = AudioFileClip(audio_path)
        duration_seconds = int(audio_clip.duration) if audio_clip.duration else 0

        video_clip = ColorClip(size=(1280, 720), color=(0, 0, 0), duration=audio_clip.duration or 1)
        video_clip = video_clip.set_audio(audio_clip)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
            temp_path = tmp_file.name

        video_clip.write_videofile(
            temp_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            verbose=False,
            logger=None,
        )

        filename = _build_video_filename(video)
        with open(temp_path, "rb") as generated_file:
            video.video_file.save(filename, File(generated_file), save=False)

        video.duration_seconds = duration_seconds
        video.file_size_bytes = os.path.getsize(video.video_file.path)
        video.status = "ready"
        video.generation_progress = 100
        video.generation_time_ms = int((time.monotonic() - start_time) * 1000)
        video.save()

        logger.info("Video generation succeeded for video %s", video.pk)
    except Exception as exc:  # pragma: no cover - exercised indirectly via view
        logger.exception("Video generation failed for video %s", video.pk)
        video.status = "failed"
        video.error_message = str(exc)
        video.save(update_fields=["status", "error_message", "updated_at"])
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                logger.warning("Could not remove temporary video file at %s", temp_path)

        for clip in [locals().get("audio_clip"), locals().get("video_clip")]:
            if clip:
                try:
                    clip.close()
                except Exception:
                    logger.debug("Failed to close clip during cleanup", exc_info=True)

    return video
