import logging
import os
import sys
import tempfile
from dataclasses import dataclass
from typing import List, Optional

from django.conf import settings
from django.utils import timezone

from videos.styles import get_default_prompt_for_style, get_style_label

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
    install_hint = (
        "Install dependencies with the same interpreter you use for manage.py, e.g. "
        f"`{sys.executable} -m pip install -r requirements.txt`."
    )
    try:
        import moviepy.editor as moviepy_editor
        from moviepy.editor import AudioFileClip, ColorClip, VideoFileClip  # noqa: F401
    except Exception as exc:  # pragma: no cover - exercised via tests
        raise VideoGenerationError(
            f"MoviePy could not be loaded: {exc}. {install_hint}",
            code="moviepy_missing",
        ) from exc

    required_attrs = ["AudioFileClip", "ColorClip", "VideoFileClip"]
    missing = [attr for attr in required_attrs if not hasattr(moviepy_editor, attr)]
    if missing:
        raise VideoGenerationError(
            (
                "MoviePy is installed but missing editor utilities: "
                f"{', '.join(missing)}. {install_hint}"
            ),
            code="moviepy_missing",
        )

    return moviepy_editor


def build_final_prompt(video) -> str:
    style_label = get_style_label(getattr(video, "style", ""))
    style_prompt = getattr(video, "style_prompt", "") or get_default_prompt_for_style(
        getattr(video, "style", "")
    )
    lyrics = getattr(getattr(video, "audio_track", None), "lyrics", "") or "No lyrics provided."
    extra = getattr(video, "extra_prompt", "") or "No additional instructions."
    parts = [
        f"Music video style: {style_label}",
        "",
        "Style description:",
        style_prompt,
        "",
        "Lyrics:",
        lyrics,
        "",
        "Extra instructions:",
        extra,
    ]
    return "\n".join(parts)


def _save_processing_state(video):
    update_fields: List[str] = []
    if hasattr(video, "status"):
        video.status = "processing"
        update_fields.append("status")
    if hasattr(video, "generation_progress"):
        video.generation_progress = 0
        update_fields.append("generation_progress")
    if hasattr(video, "error_message"):
        video.error_message = ""
        update_fields.append("error_message")
    if hasattr(video, "error_code"):
        video.error_code = ""
        update_fields.append("error_code")
    if hasattr(video, "last_error_message"):
        video.last_error_message = ""
        update_fields.append("last_error_message")
    if hasattr(video, "last_error_at"):
        video.last_error_at = None
        update_fields.append("last_error_at")

    if update_fields:
        video.save(update_fields=update_fields)


def _save_failure_state(video, exc: Exception):
    update_fields: List[str] = []
    if hasattr(video, "status"):
        video.status = "failed"
        update_fields.append("status")
    if hasattr(video, "error_message"):
        video.error_message = str(exc)
        update_fields.append("error_message")
    if hasattr(video, "last_error_message"):
        video.last_error_message = str(exc)
        update_fields.append("last_error_message")
    if hasattr(video, "last_error_at"):
        video.last_error_at = timezone.now()
        update_fields.append("last_error_at")
    if hasattr(video, "generation_progress"):
        video.generation_progress = 0
        update_fields.append("generation_progress")
    if hasattr(video, "generation_log"):
        _append_log(video, [f"Generation failed: {exc}"])
        update_fields.append("generation_log")

    if update_fields:
        video.save(update_fields=update_fields)


def generate_video_for_instance(video):
    """Generate an MP4 for a GeneratedVideo instance using MoviePy."""

    log_entries: List[str] = []

    def log_step(message: str) -> None:
        logger.info(message)
        log_entries.append(message)

    log_step(f"Starting video generation for video {getattr(video, 'pk', '<unsaved>')}")
    _save_processing_state(video)

    try:
        editor = _load_moviepy()

        audio_file_field = getattr(getattr(video, "audio_track", None), "audio_file", None)
        background_file_field = getattr(getattr(video, "background_video", None), "video_file", None)

        if not audio_file_field or not getattr(audio_file_field, "name", None):
            raise VideoGenerationError("Audio file is missing for this video.", code="audio_missing")

        audio_path = os.path.join(settings.MEDIA_ROOT, audio_file_field.name)
        if not os.path.exists(audio_path):
            raise VideoGenerationError("Audio file is missing for this video.", code="audio_missing")

        output_dir = os.path.join(settings.MEDIA_ROOT, "generated_videos")
        os.makedirs(output_dir, exist_ok=True)
        output_filename = f"generated_{video.id}.mp4"
        output_path = os.path.join(output_dir, output_filename)

        log_step("Loading media clips")
        audio_clip = bg_clip = final_clip = None
        width = height = None
        try:
            audio_clip = editor.AudioFileClip(audio_path)
            duration = float(getattr(audio_clip, "duration", 0) or 0)
            if duration <= 0:
                duration = 3.0

            if background_file_field and getattr(background_file_field, "name", None):
                bg_path = os.path.join(settings.MEDIA_ROOT, background_file_field.name)
                if not os.path.exists(bg_path):
                    raise VideoGenerationError(
                        "Background video is missing for this video.", code="background_missing"
                    )
                bg_clip = editor.VideoFileClip(bg_path).subclip(0, duration)
            else:
                bg_clip = editor.ColorClip(size=(1280, 720), color=(20, 40, 80), duration=duration)

            final_clip = bg_clip.set_audio(audio_clip)

            log_step(f"Writing combined video to {output_path}")
            final_clip.write_videofile(
                output_path,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                verbose=False,
                logger=None,
            )
        finally:
            if final_clip:
                final_clip.close()
            if bg_clip:
                bg_clip.close()
            if audio_clip:
                audio_clip.close()

        if not os.path.exists(output_path):
            raise VideoGenerationError("Generated video file was not created.")

        relative_output = os.path.join("generated_videos", output_filename)
        if hasattr(video, "video_file"):
            video.video_file.name = relative_output
        if hasattr(video, "duration_seconds"):
            video.duration_seconds = int(duration)
        if hasattr(video, "status"):
            video.status = "ready"
        if hasattr(video, "last_error_message"):
            video.last_error_message = ""
        if hasattr(video, "last_error_at"):
            video.last_error_at = None
        if hasattr(video, "generation_progress"):
            video.generation_progress = 100
        if hasattr(video, "file_size_bytes"):
            video.file_size_bytes = os.path.getsize(output_path)
        if hasattr(video, "resolution") and bg_clip is not None:
            width = getattr(bg_clip, "w", width)
            height = getattr(bg_clip, "h", height)
            if width and height:
                video.resolution = f"{int(width)}x{int(height)}"
                video.aspect_ratio = f"{int(width)}:{int(height)}"

        update_fields = [
            field
            for field in [
                "video_file",
                "duration_seconds",
                "status",
                "last_error_message",
                "last_error_at",
                "generation_progress",
                "file_size_bytes",
                "resolution",
                "aspect_ratio",
                "generation_log",
            ]
            if hasattr(video, field)
        ]
        if hasattr(video, "generation_log"):
            log_entries.append("Video generation completed successfully.")
            _append_log(video, log_entries)

        video.save(update_fields=update_fields)

        log_step(f"Video generation succeeded for video {getattr(video, 'pk', '<unsaved>')}")
        return video

    except VideoGenerationError as exc:
        logger.exception("Video generation failed for video %s", getattr(video, "pk", "<unsaved>"))
        log_step(f"Generation failed: {exc}")
        _append_log(video, log_entries)
        _save_failure_state(video, exc)
        return video
    except Exception as exc:  # pragma: no cover - surface errors to caller
        logger.exception("Video generation failed for video %s", getattr(video, "pk", "<unsaved>"))
        log_step(f"Generation failed: {exc}")
        _append_log(video, log_entries)
        _save_failure_state(video, exc)
        return video


def generate_lyric_video_for_instance(video):
    """Generate a lyric video using an existing background clip and audio track."""

    log_entries: List[str] = []

    def log_step(message: str) -> None:
        logger.info(message)
        log_entries.append(message)

    try:
        if not getattr(video, "style_prompt", ""):
            video.style_prompt = get_default_prompt_for_style(getattr(video, "style", ""))
        video.prompt_used = build_final_prompt(video)
        video.save(update_fields=["style_prompt", "prompt_used"])

        video.status = "processing"
        video.generation_progress = 10
        video.error_message = ""
        video.last_error_message = ""
        video.save(update_fields=["status", "generation_progress", "error_message", "last_error_message"])

        audio_track = getattr(video, "audio_track", None)
        audio_file_field = getattr(audio_track, "audio_file", None)
        if not audio_track or not audio_file_field or not audio_file_field.name:
            raise VideoGenerationError("Audio file is missing for this video.", code="audio_missing")

        bg_field: Optional[object] = getattr(video, "background_video", None)
        bg_file_field = getattr(bg_field, "video_file", None)
        if not bg_file_field or not getattr(bg_file_field, "name", ""):
            raise VideoGenerationError("Background video is required for lyric generation.", code="background_missing")

        audio_path = os.path.join(settings.MEDIA_ROOT, audio_file_field.name)
        bg_path = os.path.join(settings.MEDIA_ROOT, bg_file_field.name)
        if not os.path.exists(audio_path):
            raise VideoGenerationError("Audio file not found on disk.", code="audio_missing")
        if not os.path.exists(bg_path):
            raise VideoGenerationError("Background video file not found on disk.", code="background_missing")

        log_step(f"Loading audio from {audio_path}")
        log_step(f"Loading background video from {bg_path}")

        try:
            from moviepy.editor import AudioFileClip as MPYAudioFileClip
            from moviepy.editor import CompositeVideoClip, TextClip, VideoFileClip as MPYVideoFileClip
        except ModuleNotFoundError:  # pragma: no cover - fallback for minimal installs
            from moviepy import AudioFileClip as MPYAudioFileClip  # type: ignore
            from moviepy import CompositeVideoClip, TextClip, VideoFileClip as MPYVideoFileClip  # type: ignore

        audio_clip = None
        bg_clip = None
        final_clip = None
        try:
            audio_clip = MPYAudioFileClip(audio_path)
            bg_clip = MPYVideoFileClip(bg_path).resize((1280, 720))

            duration = min(bg_clip.duration or 0, audio_clip.duration or 0) or audio_clip.duration or bg_clip.duration or 0
            duration = float(duration)
            if duration <= 0:
                raise VideoGenerationError("Unable to determine duration for video composition.", code="duration_invalid")

            lyrics_text = getattr(audio_track, "lyrics", "") or ""
            txt_clip = (
                TextClip(
                    txt=lyrics_text,
                    fontsize=50,
                    color="white",
                    stroke_color="black",
                    stroke_width=3,
                    method="caption",
                    size=(1000, 600),
                )
                .set_position("center")
                .set_duration(duration)
            )

            final_clip = CompositeVideoClip([bg_clip.set_duration(duration), txt_clip]).set_audio(audio_clip)

            output_dir = os.path.join(settings.MEDIA_ROOT, "generated_videos")
            os.makedirs(output_dir, exist_ok=True)
            output_relative = f"generated_videos/generated_{video.id}.mp4"
            output_full_path = os.path.join(settings.MEDIA_ROOT, output_relative)

            log_step(f"Writing lyric video to {output_full_path}")
            final_clip.write_videofile(
                output_full_path,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                verbose=False,
                logger=None,
            )

        finally:
            if final_clip:
                final_clip.close()
            if bg_clip:
                bg_clip.close()
            if audio_clip:
                audio_clip.close()

        if not os.path.exists(output_full_path):
            raise VideoGenerationError("Lyric video file was not created.", code="output_missing")

        video.video_file.name = output_relative
        video.file_size_bytes = os.path.getsize(output_full_path)
        video.duration_seconds = int(duration)
        video.resolution = "1280x720"
        video.aspect_ratio = "16:9"
        video.status = "ready"
        video.generation_progress = 100
        video.generation_time_ms = video.generation_time_ms or 0

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

    except Exception as exc:
        logger.exception("Lyric video generation failed", exc_info=exc)
        log_step(f"Generation failed: {exc}")
        _append_log(video, log_entries)
        video.status = "failed"
        video.error_message = str(exc)
        video.last_error_message = str(exc)
        video.generation_progress = 0
        video.save(
            update_fields=[
                "status",
                "error_message",
                "last_error_message",
                "generation_progress",
                "generation_log",
            ]
        )
        raise
