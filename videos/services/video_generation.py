import logging
import os
from dataclasses import dataclass
from pathlib import Path
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
    try:
        import moviepy.editor as moviepy_editor  # type: ignore
    except Exception as exc:  # pragma: no cover - handled gracefully
        raise VideoGenerationError(
            "MoviePy is not available. Install the 'moviepy' package to enable video generation.",
            code="moviepy_missing",
        ) from exc

    required_attrs = ("AudioFileClip", "VideoFileClip")
    missing = [name for name in required_attrs if not hasattr(moviepy_editor, name)]
    if missing:
        raise VideoGenerationError(
            "MoviePy installation is incomplete; reinstall the 'moviepy' package to restore editor components.",
            code="moviepy_incomplete",
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


def generate_video_for_instance(video):
    """Generate a real MP4 for a GeneratedVideo instance using MoviePy."""

    log_entries: List[str] = []

    def log_step(message: str) -> None:
        logger.info(message)
        log_entries.append(message)

    logger.info("Starting video generation for GeneratedVideo %s", video.pk)

    video.status = "processing"
    video.generation_progress = 10
    video.error_message = ""
    video.error_code = ""
    video.last_error_message = ""
    video.last_error_at = None
    video.save(
        update_fields=[
            "status",
            "generation_progress",
            "error_message",
            "error_code",
            "last_error_message",
            "last_error_at",
        ]
    )

    try:
        audio_field = getattr(video, "audio_track", None)
        audio_file_field = getattr(audio_field, "audio_file", None)
        if not audio_file_field or not audio_file_field.name:
            raise VideoGenerationError("Audio file is missing for this video.", code="audio_missing")

        bg_field = getattr(video, "background_video", None)
        bg_file_field = getattr(bg_field, "video_file", None)
        if not bg_file_field or not bg_file_field.name:
            raise VideoGenerationError("Background video is missing for this video.", code="background_missing")

        audio_path = os.path.join(settings.MEDIA_ROOT, audio_file_field.name)
        bg_path = os.path.join(settings.MEDIA_ROOT, bg_file_field.name)

        if not os.path.exists(audio_path):
            raise VideoGenerationError("Audio file not found on disk.", code="audio_missing")
        if not os.path.exists(bg_path):
            raise VideoGenerationError("Background video file not found on disk.", code="background_missing")

        log_step(f"Loading background video from {bg_path}")
        log_step(f"Loading audio from {audio_path}")

        editor = _load_moviepy()
        AudioFileClip = getattr(editor, "AudioFileClip")
        VideoFileClip = getattr(editor, "VideoFileClip")

        bg_clip = None
        audio_clip = None
        final_clip = None
        trimmed_bg = None
        trimmed_audio = None

        try:
            bg_clip = VideoFileClip(bg_path)
            audio_clip = AudioFileClip(audio_path)

            bg_duration = float(bg_clip.duration or 0)
            audio_duration = float(audio_clip.duration or 0)
            duration = min(bg_duration, audio_duration)

            if duration <= 0:
                raise VideoGenerationError("Unable to determine duration for composition.", code="duration_invalid")

            trimmed_bg = bg_clip.subclip(0, duration)
            trimmed_audio = audio_clip.subclip(0, duration)
            final_clip = trimmed_bg.set_audio(trimmed_audio).set_duration(duration)

            output_dir = Path(settings.MEDIA_ROOT) / "generated_videos"
            output_dir.mkdir(parents=True, exist_ok=True)

            output_relative = f"generated_videos/generated_{video.id}.mp4"
            output_full_path = os.path.join(settings.MEDIA_ROOT, output_relative)

            log_step(f"Writing composed video to {output_full_path}")
            final_clip.write_videofile(
                output_full_path,
                fps=bg_clip.fps or 24,
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
            raise VideoGenerationError("Generated video file was not created.", code="output_missing")

        video.video_file.name = output_relative
        video.file_size_bytes = os.path.getsize(output_full_path)
        video.duration_seconds = int(duration)
        video.resolution = f"{int(trimmed_bg.w)}x{int(trimmed_bg.h)}"
        video.aspect_ratio = f"{int(trimmed_bg.w)}:{int(trimmed_bg.h)}"
        video.status = "ready"
        video.generation_progress = 100
        video.generation_time_ms = video.generation_time_ms or 0
        video.last_error_message = ""
        video.last_error_at = None

        log_step("Video generation succeeded")
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
                "last_error_message",
                "last_error_at",
            ]
        )
        return video

    except VideoGenerationError as exc:
        log_step(f"Generation failed: {exc}")
        _append_log(video, log_entries)
        video.status = "failed"
        video.error_message = str(exc)
        video.error_code = exc.code
        video.last_error_message = str(exc)
        video.last_error_at = timezone.now()
        video.generation_progress = 0
        video.save(
            update_fields=[
                "status",
                "error_message",
                "error_code",
                "last_error_message",
                "last_error_at",
                "generation_progress",
                "generation_log",
            ]
        )
        return video
    except Exception as exc:  # pragma: no cover - defensive catch
        logger.exception("Unexpected error during video generation")
        log_step(f"Generation failed: {exc}")
        _append_log(video, log_entries)
        video.status = "failed"
        video.error_message = str(exc)
        video.last_error_message = str(exc)
        video.last_error_at = timezone.now()
        video.generation_progress = 0
        video.save(
            update_fields=[
                "status",
                "error_message",
                "last_error_message",
                "last_error_at",
                "generation_progress",
                "generation_log",
            ]
        )
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
        video.save(
            update_fields=["status", "generation_progress", "error_message", "last_error_message"]
        )

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

        from moviepy.editor import AudioFileClip, CompositeVideoClip, TextClip, VideoFileClip

        audio_clip = None
        bg_clip = None
        final_clip = None
        try:
            audio_clip = AudioFileClip(audio_path)
            bg_clip = VideoFileClip(bg_path).resize((1280, 720))

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
        return video
