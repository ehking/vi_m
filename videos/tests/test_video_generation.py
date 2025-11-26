import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from videos.models import AudioTrack, GeneratedVideo
from videos.services import generate_video_for_instance
from videos.services.video_generation import FALLBACK_VIDEO_BYTES, VideoGenerationError


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class GenerateVideoServiceTest(TestCase):
    def setUp(self):
        audio_file = SimpleUploadedFile("audio.mp3", b"audio-bytes", content_type="audio/mpeg")
        self.audio = AudioTrack.objects.create(title="Track", audio_file=audio_file)

    def test_generate_video_success(self):
        video = GeneratedVideo.objects.create(audio_track=self.audio, title="Video Success")

        def write_file_side_effect(path, *args, **kwargs):
            Path(path).write_bytes(b"video-bytes")

        audio_instance = MagicMock()
        audio_instance.duration = 2

        color_instance = MagicMock()
        final_clip = MagicMock()
        color_instance.set_audio.return_value = final_clip
        final_clip.write_videofile.side_effect = write_file_side_effect

        editor_mock = MagicMock()
        editor_mock.AudioFileClip = MagicMock(return_value=audio_instance)
        editor_mock.ColorClip = MagicMock(return_value=color_instance)

        with patch("videos.services.video_generation._load_moviepy", return_value=editor_mock):
            generate_video_for_instance(video)

        video.refresh_from_db()
        self.assertEqual(video.status, "ready")
        self.assertEqual(video.duration_seconds, 2)
        self.assertTrue(video.video_file.name)
        self.assertGreaterEqual(video.file_size_bytes or 0, 0)
        self.assertIn("Starting video generation", video.generation_log)

    def test_generate_video_failure(self):
        video = GeneratedVideo.objects.create(audio_track=self.audio, title="Video Failure")

        editor_mock = MagicMock()
        editor_mock.AudioFileClip = MagicMock(side_effect=Exception("boom"))
        editor_mock.ColorClip = MagicMock()

        with patch("videos.services.video_generation._load_moviepy", return_value=editor_mock):
            generate_video_for_instance(video)

        video.refresh_from_db()
        self.assertEqual(video.status, "failed")
        self.assertIn("boom", video.error_message)
        self.assertIn("Generation failed", video.generation_log)
        self.assertTrue(editor_mock.AudioFileClip.called)

    def test_generate_video_fallback_when_moviepy_missing(self):
        video = GeneratedVideo.objects.create(audio_track=self.audio, title="Video Missing MoviePy")

        with patch(
            "videos.services.video_generation._load_moviepy",
            side_effect=VideoGenerationError(
                "MoviePy is not available. Install the 'moviepy' package to enable video generation.",
                code="moviepy_missing",
            ),
        ):
            generate_video_for_instance(video)

        video.refresh_from_db()
        self.assertEqual(video.status, "ready")
        self.assertEqual(video.generation_progress, 100)
        self.assertTrue(video.video_file.name)
        self.assertTrue(video.video_file.path.endswith(".mp4"))
        self.assertTrue(video.video_file.storage.exists(video.video_file.name))
        self.assertGreater(video.file_size_bytes or 0, 0)
        with open(video.video_file.path, "rb") as f:
            self.assertEqual(f.read(), FALLBACK_VIDEO_BYTES)
        self.assertIn("placeholder video file", video.generation_log)
