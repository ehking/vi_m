import importlib.util
import os
import tempfile
from unittest import skipUnless
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from videos.models import AudioTrack, GeneratedVideo


MOVIEPY_EDITOR_AVAILABLE = importlib.util.find_spec("moviepy.editor") is not None


@skipUnless(MOVIEPY_EDITOR_AVAILABLE, "moviepy.editor is required for sample video command tests")
class CreateSampleVideoCommandTest(TestCase):
    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_creates_sample_audio_and_video(self):
        call_command("create_sample_video", title="Demo Clip")

        audio = AudioTrack.objects.get(title="Sample Audio Track")
        video = GeneratedVideo.objects.get(title="Demo Clip")

        self.assertEqual(audio.artist, "System")
        self.assertEqual(video.audio_track, audio)
        self.assertEqual(video.status, "ready")
        self.assertEqual(video.generation_progress, 100)

        self.assertTrue(os.path.exists(audio.audio_file.path))
        self.assertTrue(os.path.exists(video.video_file.path))
        self.assertGreater(video.file_size_bytes or 0, 0)

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_force_regenerates_files(self):
        call_command("create_sample_video")
        video = GeneratedVideo.objects.get(title="Sample Video")
        original_path = video.video_file.path
        self.assertTrue(os.path.exists(original_path))

        # Remove the file to simulate missing artifact and force recreation
        os.remove(original_path)
        call_command("create_sample_video", force=True)

        video.refresh_from_db()
        self.assertTrue(os.path.exists(video.video_file.path))
        self.assertEqual(video.status, "ready")
        self.assertEqual(video.generation_progress, 100)


class CreateSampleVideoCommandMissingDepsTest(TestCase):
    def test_requires_moviepy_with_install_hint(self):
        with patch(
            "videos.management.commands.create_sample_video.importlib.import_module",
            side_effect=ImportError("No module named 'moviepy.editor'"),
        ):
            with self.assertRaisesMessage(CommandError, "Install dependencies with"):
                call_command("create_sample_video")
