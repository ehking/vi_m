import logging
import os
import importlib
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.core.files import File

from videos.models import GeneratedVideo

logger = logging.getLogger(__name__)


def _load_moviepy():
    return importlib.import_module("moviepy.editor")


def _append_log(video: GeneratedVideo, entry: str) -> None:
    log_entry = str(entry)
    if video.generation_log:
        video.generation_log = f"{video.generation_log}\n{log_entry}"
    else:
        video.generation_log = log_entry


def _prepare_output_path(video: GeneratedVideo) -> Path:
    output_dir = Path(settings.MEDIA_ROOT) / "videos"
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"generated_{video.pk or 'temp'}.mp4"
    return output_dir / filename


def generate_video_for_instance(video: GeneratedVideo) -> GeneratedVideo:
    """Generate a placeholder video synchronized with the audio track.

    The heavy lifting uses MoviePy, but imports are deferred so unit tests can
    mock the behaviour without requiring the dependency. The function updates
    the ``GeneratedVideo`` instance in-place and returns it.
    """

    video.status = "processing"
    video.error_message = ""
    video.generation_progress = 10
    _append_log(video, "Starting video generation")
    video.save(update_fields=["status", "error_message", "generation_progress", "generation_log"])

    output_path: Optional[Path] = None
    audio_clip = None
    color_clip = None
    final_clip = None

    try:
        editor = _load_moviepy()
        AudioFileClip = editor.AudioFileClip
        ColorClip = editor.ColorClip

        audio_path = getattr(video.audio_track.audio_file, "path", None)
        if not audio_path or not os.path.exists(audio_path):
            raise FileNotFoundError("Audio file is missing for the selected track.")

        audio_clip = AudioFileClip(audio_path)
        duration = float(audio_clip.duration or 1.0)
        color_clip = ColorClip(size=(1280, 720), color=(0, 0, 0), duration=duration)
        final_clip = color_clip.set_audio(audio_clip)

        output_path = _prepare_output_path(video)
        final_clip.write_videofile(str(output_path), codec="libx264", audio_codec="aac", verbose=False, logger=None)

        if output_path.exists():
            with output_path.open("rb") as fh:
                video.video_file.save(output_path.name, File(fh), save=False)
            video.file_size_bytes = output_path.stat().st_size
        video.duration_seconds = int(duration)
        video.status = "ready"
        video.generation_progress = 100
        _append_log(video, "Video generation completed")
        video.save(
            update_fields=[
                "video_file",
                "file_size_bytes",
                "duration_seconds",
                "status",
                "generation_progress",
                "generation_log",
            ]
        )
        return video
    except Exception as exc:  # noqa: BLE001
        logger.exception("Video generation failed", exc_info=exc)
        video.status = "failed"
        video.error_message = str(exc)
        _append_log(video, f"Generation failed: {exc}")
        video.save(update_fields=["status", "error_message", "generation_log"])
        return video
    finally:
        for clip in (final_clip, color_clip, audio_clip):
            close_method = getattr(clip, "close", None)
            if callable(close_method):
                try:
                    close_method()
                except Exception:  # pragma: no cover - best effort cleanup
                    logger.debug("Failed to close clip", exc_info=True)

        # Clean up temporary output file if the model persisted it elsewhere
        if output_path and output_path.exists() and video.video_file.name != f"videos/{output_path.name}":
            try:
                output_path.unlink()
            except OSError:
                logger.debug("Failed to remove temporary video file %s", output_path, exc_info=True)
