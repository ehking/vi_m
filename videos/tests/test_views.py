import os
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from videos.models import AudioTrack, GeneratedVideo


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class GenerateAIVideoViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="tester", password="password")
        self.client.login(username="tester", password="password")

        self.audio = AudioTrack.objects.create(
            title="Song", artist="Artist", audio_file=SimpleUploadedFile("song.mp3", b"audio", content_type="audio/mpeg")
        )
        self.video = GeneratedVideo.objects.create(audio_track=self.audio, title="Draft", status="pending")

    def test_generate_ai_video_success(self):
        with mock.patch("videos.views.generate_video_for_audio") as generate_mock:
            generate_mock.return_value = (b"video-bytes", 42)

            response = self.client.post(reverse("generate-ai-video", args=[self.video.pk]))

        self.assertRedirects(response, reverse("video-detail", args=[self.video.pk]))
        self.video.refresh_from_db()

        self.assertEqual(self.video.status, "ready")
        self.assertEqual(self.video.duration_seconds, 42)
        self.assertFalse(self.video.error_message)
        self.assertTrue(self.video.video_file.name.endswith(".mp4"))
        self.assertTrue(os.path.exists(self.video.video_file.path))

    def test_generate_ai_video_failure(self):
        with mock.patch("videos.views.generate_video_for_audio") as generate_mock:
            generate_mock.side_effect = RuntimeError("moviepy exploded")

            response = self.client.post(reverse("generate-ai-video", args=[self.video.pk]))

        self.assertRedirects(response, reverse("video-detail", args=[self.video.pk]))
        self.video.refresh_from_db()

        self.assertEqual(self.video.status, "failed")
        self.assertIn("moviepy exploded", self.video.error_message)
        self.assertFalse(self.video.video_file)
        self.assertIsNone(self.video.duration_seconds)
