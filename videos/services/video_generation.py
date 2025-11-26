import logging
import os
import tempfile
import time
from dataclasses import dataclass
from typing import Iterable, List

from django.core.files import File
from django.utils import timezone

from videos.models import GeneratedVideo

logger = logging.getLogger(__name__)


class VideoGenerationError(Exception):
    """Raised when AI video generation fails."""


@dataclass
class _GenerationContext:
    video: GeneratedVideo
    log_entries: List[str]

    def append_log(self, message: str) -> None:
        timestamp = timezone.now().isoformat()
        entry = f"[{timestamp}] {message}"
        self.log_entries.append(entry)

    def flush_logs(self) -> None:
        if not self.log_entries:
            return
        combined_log = "\n".join(self.log_entries)
        if self.video.generation_log:
            self.video.generation_log = f"{self.video.generation_log}\n{combined_log}"
        else:
            self.video.generation_log = combined_log
        self.log_entries.clear()


def _validate_audio_path(video: GeneratedVideo) -> str:
    audio_file = getattr(video.audio_track, "audio_file", None)
    if not audio_file or not getattr(audio_file, "path", None):
        raise VideoGenerationError("Audio file is required to generate the video.")

    audio_path = audio_file.path
    if not os.path.exists(audio_path):
        raise VideoGenerationError("Audio file could not be found on disk.")
    return audio_path


def _update_metadata(video: GeneratedVideo, *, file_path: str, duration: float, resolution: Iterable[int]) -> None:
    width, height = resolution
    video.file_size_bytes = os.path.getsize(file_path)
    video.duration_seconds = int(duration)
    video.resolution = f"{width}x{height}"
    aspect_ratio = round(width / height, 2) if height else 0
    video.aspect_ratio = f"{aspect_ratio}:1" if aspect_ratio else ""


def _write_video_file(context: _GenerationContext, *, temp_path: str, resolution: Iterable[int], audio_path: str) -> float:
    try:
        from moviepy.editor import AudioFileClip, ColorClip, CompositeVideoClip
    except ImportError as exc:  # pragma: no cover - exercised when dependency missing
        raise VideoGenerationError(
            "MoviePy is required to generate videos. Please install moviepy to continue."
        ) from exc

    width, height = resolution
    context.append_log("Loading audio track into MoviePy.")
    with AudioFileClip(audio_path) as audio_clip:
        duration = max(audio_clip.duration, 1.0)
        context.append_log(f"Audio duration detected: {duration:.2f}s. Creating visual clip.")
        color_clip = ColorClip(size=(width, height), color=(0, 0, 0), duration=duration)
        composite_clip = CompositeVideoClip([color_clip]).set_audio(audio_clip)
        context.append_log("Writing rendered video to temporary file.")
        composite_clip.write_videofile(
            temp_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            verbose=False,
            logger=None,
        )
        composite_clip.close()
    return duration


def generate_video_for_instance(video: GeneratedVideo) -> GeneratedVideo:
    """
    Receives a GeneratedVideo instance (or equivalent model).
    Updates its status and fields while generating a video file with MoviePy.
    Logs each major step.
    Returns the updated instance.
    """

    context = _GenerationContext(video=video, log_entries=[])
    start = time.perf_counter()
    temp_file_path = None
    resolution = (1280, 720)
    context.append_log("Starting AI video generation.")
    video.status = "processing"
    video.generation_progress = 10
    video.error_message = ""
    video.error_code = ""
    context.flush_logs()
    video.save(update_fields=["status", "generation_progress", "error_message", "error_code", "generation_log"])

    try:
        audio_path = _validate_audio_path(video)
        logger.info("[Video %s] Audio validation successful.", video.pk)
        context.append_log("Audio validation successful.")
        context.flush_logs()

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
            temp_file_path = temp_file.name

        context.append_log("Generating video content with MoviePy.")
        context.flush_logs()
        duration = _write_video_file(context, temp_path=temp_file_path, resolution=resolution, audio_path=audio_path)
        context.flush_logs()

        filename = f"generated_video_{video.pk or int(time.time())}.mp4"
        context.append_log("Attaching generated video file to model.")
        with open(temp_file_path, "rb") as generated_file:
            video.video_file.save(filename, File(generated_file), save=False)

        _update_metadata(video, file_path=temp_file_path, duration=duration, resolution=resolution)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        video.generation_time_ms = elapsed_ms
        video.status = "ready"
        video.generation_progress = 100
        context.append_log(f"Video generation completed successfully in {elapsed_ms} ms.")
        context.flush_logs()
        video.save(
            update_fields=[
                "video_file",
                "file_size_bytes",
                "duration_seconds",
                "resolution",
                "aspect_ratio",
                "generation_time_ms",
                "status",
                "generation_progress",
                "generation_log",
            ]
        )
        logger.info("[Video %s] Generation finished.", video.pk)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[Video %s] Video generation failed.", video.pk)
        context.append_log(f"Video generation failed: {exc}")
        video.status = "failed"
        video.generation_progress = 0
        video.error_message = str(exc)
        video.error_code = exc.__class__.__name__
        context.flush_logs()
        video.save(
            update_fields=[
                "status",
                "generation_progress",
                "error_message",
                "error_code",
                "generation_log",
            ]
        )
        raise VideoGenerationError(str(exc)) from exc
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError:
                logger.warning("Failed to clean up temporary file %s", temp_file_path)

    return video
