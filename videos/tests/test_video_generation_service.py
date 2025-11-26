import importlib.util
import os
import tempfile
import wave
from unittest import skipUnless

from django.core.files import File
from django.test import TestCase, override_settings

from videos.models import AudioTrack, GeneratedVideo
from videos.services.video_generation import generate_video_for_instance


MOVIEPY_AVAILABLE = importlib.util.find_spec("moviepy") is not None


@skipUnless(MOVIEPY_AVAILABLE, "moviepy is required for video generation tests")
class VideoGenerationServiceTest(TestCase):
    def _create_silent_audio(self, path: str) -> None:
        with wave.open(path, "w") as wave_file:
            wave_file.setnchannels(1)
            wave_file.setsampwidth(2)
            wave_file.setframerate(44100)
            wave_file.writeframes(b"\x00\x00" * 44100)

    def test_generate_video_updates_instance(self):
        with tempfile.TemporaryDirectory() as tmpdir, override_settings(MEDIA_ROOT=tmpdir):
            audio_path = os.path.join(tmpdir, "audio.wav")
            self._create_silent_audio(audio_path)

            with open(audio_path, "rb") as audio_file:
                audio_track = AudioTrack.objects.create(
                    title="Test Audio",
                    audio_file=File(audio_file, name="audio.wav"),
                )

            video = GeneratedVideo.objects.create(audio_track=audio_track, title="AI Video")

            generate_video_for_instance(video)
            video.refresh_from_db()

            self.assertEqual(video.status, "ready")
            self.assertEqual(video.generation_progress, 100)
            self.assertTrue(video.video_file.name)
            self.assertTrue(os.path.exists(video.video_file.path))
            self.assertGreater(video.file_size_bytes or 0, 0)
            self.assertIn("Video generation completed", video.generation_log)
