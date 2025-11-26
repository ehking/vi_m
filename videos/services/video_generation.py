import os
from typing import Optional

from django.conf import settings

try:  # pragma: no cover - dependency guard
    from moviepy.editor import AudioFileClip, ColorClip
except Exception:  # pragma: no cover - dependency guard
    AudioFileClip = None
    ColorClip = None

from videos.models import GeneratedVideo


class VideoGenerationError(Exception):
    """Raised when video generation fails."""


def generate_video_for_instance(video: GeneratedVideo) -> GeneratedVideo:
    """Generate a simple video for the provided ``GeneratedVideo`` instance.

    The function updates the instance status, saves the generated video to
    ``MEDIA_ROOT`` and records metadata. Errors are captured on the model.
    """

    video.status = "processing"
    video.error_message = ""
    video.save(update_fields=["status", "error_message"])

    try:
        clip, audio_clip = _build_clip(video)
        output_path = _write_video_file(video, clip)
        _update_video_fields(video, audio_clip, output_path)
        return video
    except Exception as exc:  # pragma: no cover - error handling path tested separately
        video.status = "failed"
        video.error_message = str(exc)
        video.save(update_fields=["status", "error_message"])
        raise VideoGenerationError(str(exc)) from exc
    finally:
        if "clip" in locals() and clip is not None:
            try:
                clip.close()
            except Exception:
                pass
        if "audio_clip" in locals() and audio_clip is not None:
            try:
                audio_clip.close()
            except Exception:
                pass


def _build_clip(video: GeneratedVideo):
    if AudioFileClip is None or ColorClip is None:
        raise ImportError("moviepy is required for video generation")

    audio_clip = AudioFileClip(video.audio_track.audio_file.path)
    clip = ColorClip(size=(1280, 720), color=(0, 0, 0), duration=audio_clip.duration)
    clip = clip.set_audio(audio_clip)
    return clip, audio_clip


def _write_video_file(video: GeneratedVideo, clip) -> str:
    media_root = getattr(settings, "MEDIA_ROOT", None) or "."
    output_dir = os.path.join(media_root, "videos")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"generated_{video.pk}.mp4")
    clip.write_videofile(output_path, codec="libx264", audio_codec="aac", verbose=False, logger=None)
    return output_path


def _update_video_fields(video: GeneratedVideo, audio_clip, output_path: str) -> None:
    relative_path = os.path.relpath(output_path, getattr(settings, "MEDIA_ROOT", "."))
    video.video_file.name = relative_path
    duration = getattr(audio_clip, "duration", None)
    video.duration_seconds = int(duration) if duration is not None else None
    video.status = "ready"
    video.generation_progress = 100
    video.save(update_fields=["video_file", "duration_seconds", "status", "generation_progress"])


__all__ = ["generate_video_for_instance", "VideoGenerationError"]
