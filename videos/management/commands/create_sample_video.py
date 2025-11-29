import importlib
import os
from datetime import datetime
import sys
import wave
from typing import Tuple

import numpy as np
from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from videos.models import AudioTrack, BackgroundVideo, GeneratedVideo
from videos.services.video_generation import generate_video_for_instance


class Command(BaseCommand):
    help = "Create a sample audio track and generated video for demos or local testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--title",
            default="Sample Video",
            help="Title to use for the generated sample video.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recreate sample files even if records already exist.",
        )

    def handle(self, *args, **options):
        title = options["title"]
        force = options["force"]

        self.moviepy_editor = self._require_moviepy()

        audio = self._get_or_create_audio(force=force)
        background = self._get_or_create_background_video(force=force)
        video = self._get_or_create_video(audio, background, title=title, force=force)
        video = generate_video_for_instance(video)

        self.stdout.write(
            self.style.SUCCESS(
                f"Sample video '{video.title}' ready with audio track '{audio.title}'.",
            )
        )

    def _require_moviepy(self):
        try:
            moviepy_editor = importlib.import_module("moviepy.editor")
        except Exception as exc:
            install_hint = (
                "Install dependencies with the same interpreter you use for manage.py, e.g. "
                f"`{sys.executable} -m pip install -r requirements.txt`."
            )
            raise CommandError(f"MoviePy is unavailable: {exc}. {install_hint}") from exc

        required = ["AudioClip", "AudioFileClip", "ColorClip", "VideoFileClip"]
        if not all(hasattr(moviepy_editor, attr) for attr in required):
            raise CommandError(
                "MoviePy installation is missing required editor utilities: "
                + ", ".join(required)
            )

        return moviepy_editor

    def _ensure_audio_file(self, force: bool) -> Tuple[str, int]:
        """Create a short sine-wave audio file for demo purposes."""

        os.makedirs(os.path.join(settings.MEDIA_ROOT, "audio"), exist_ok=True)
        audio_path = os.path.join(settings.MEDIA_ROOT, "audio", "sample_tone.wav")
        duration = 3

        if force or not os.path.exists(audio_path):
            clip = self.moviepy_editor.AudioClip(
                lambda t: 0.5 * np.sin(2 * np.pi * 220 * t), duration=duration
            )
            clip.write_audiofile(audio_path, fps=44100, nbytes=2, verbose=False, logger=None)
            clip.close()

        return audio_path, duration

    def _ensure_background_file(self, force: bool, duration: int) -> str:
        """Create a simple background video clip for demo purposes."""

        os.makedirs(os.path.join(settings.MEDIA_ROOT, "background_videos"), exist_ok=True)
        video_path = os.path.join(settings.MEDIA_ROOT, "background_videos", "sample_background.mp4")

        if force or not os.path.exists(video_path):
            color_clip = self.moviepy_editor.ColorClip(size=(640, 360), color=(20, 40, 80), duration=duration)
            color_clip.write_videofile(
                video_path,
                fps=24,
                codec="libx264",
                audio=False,
                verbose=False,
                logger=None,
            )
            color_clip.close()

        return video_path

    def _get_or_create_audio(self, force: bool) -> AudioTrack:
        audio_path, duration = self._ensure_audio_file(force=force)
        audio, _ = AudioTrack.objects.get_or_create(
            title="Sample Audio Track",
            defaults={
                "artist": "System",
                "lyrics": "Sample lyrics for demo playback",
                "language": "en",
                "bpm": 120,
            },
        )

        if force or not audio.audio_file:
            with open(audio_path, "rb") as fp:
                audio.audio_file.save("sample_tone.wav", File(fp), save=False)
            audio.save(update_fields=["audio_file"])

        if not audio.audio_file:
            with open(audio_path, "rb") as fp:
                audio.audio_file.save("sample_tone.wav", File(fp), save=True)

        return audio

    def _get_or_create_background_video(self, force: bool) -> BackgroundVideo:
        _, audio_duration = self._ensure_audio_file(force=False)
        video_path = self._ensure_background_file(force=force, duration=audio_duration)

        background, _ = BackgroundVideo.objects.get_or_create(title="Sample Background")

        if force or not background.video_file:
            with open(video_path, "rb") as fp:
                background.video_file.save("sample_background.mp4", File(fp), save=False)
            background.save(update_fields=["video_file"])

        if not background.video_file:
            with open(video_path, "rb") as fp:
                background.video_file.save("sample_background.mp4", File(fp), save=True)

        return background

    def _get_or_create_video(
        self, audio: AudioTrack, background: BackgroundVideo, title: str, force: bool
    ) -> GeneratedVideo:
        now = datetime.utcnow().isoformat()
        defaults = {
            "audio_track": audio,
            "background_video": background,
            "description": "Sample generated video for showcasing the dashboard.",
            "status": "pending",
            "mood": "happy",
            "tags": "sample,demo",
            "prompt_used": "Sample prompt",
            "model_name": "demo-generator",
            "generation_progress": 0,
            "generation_log": f"Queued sample video generation at {now}",
        }

        video, _ = GeneratedVideo.objects.get_or_create(title=title, defaults=defaults)

        updates = {}
        if force or not video.audio_track_id:
            updates["audio_track"] = audio
        if force or not video.background_video_id:
            updates["background_video"] = background

        if updates:
            for field, value in updates.items():
                setattr(video, field, value)
            video.save(update_fields=list(updates.keys()))

        return video
