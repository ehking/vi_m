import os
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from videos.models import AudioTrack, GeneratedVideo
from videos.services.video_generation import generate_video_for_instance, VideoGenerationError


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class GenerateVideoServiceTests(TestCase):
    def setUp(self):
        audio_file = SimpleUploadedFile("test.mp3", b"audio", content_type="audio/mpeg")
        self.audio = AudioTrack.objects.create(title="Song", audio_file=audio_file)
        self.video = GeneratedVideo.objects.create(audio_track=self.audio, title="Video")

    def test_generate_video_success(self):
        clip_mock = mock.Mock()
        clip_mock.set_audio.return_value = clip_mock
        clip_mock.write_videofile.return_value = None
        audio_mock = mock.Mock(duration=5)

        with mock.patch("videos.services.video_generation.ColorClip", return_value=clip_mock), \
                mock.patch("videos.services.video_generation.AudioFileClip", return_value=audio_mock):
            generate_video_for_instance(self.video)

        self.video.refresh_from_db()
        self.assertEqual(self.video.status, "ready")
        self.assertEqual(self.video.generation_progress, 100)
        self.assertIsNotNone(self.video.duration_seconds)
        self.assertTrue(str(self.video.video_file))

    def test_generate_video_failure(self):
        with mock.patch("videos.services.video_generation.ColorClip", side_effect=Exception("boom")):
            with self.assertRaises(VideoGenerationError):
                generate_video_for_instance(self.video)

        self.video.refresh_from_db()
        self.assertEqual(self.video.status, "failed")
        self.assertTrue(self.video.error_message)
