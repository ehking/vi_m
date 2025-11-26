import os
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from videos.models import AudioTrack, GeneratedVideo
from videos.services.video_generation import VideoGenerationError


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class GenerateVideoViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="creator", password="password")
        audio_file = SimpleUploadedFile("test.mp3", b"audio", content_type="audio/mpeg")
        self.audio = AudioTrack.objects.create(title="Song", audio_file=audio_file)
        self.video = GeneratedVideo.objects.create(audio_track=self.audio, title="Video")

    def test_generate_view_success(self):
        self.client.login(username="creator", password="password")
        generate_mock = mock.Mock()

        def _generate(video):
            video.status = "ready"
            video.video_file.name = "videos/generated.mp4"
            video.save(update_fields=["status", "video_file"])
            return video

        generate_mock.side_effect = _generate

        with mock.patch("videos.views.generate_video_for_instance", generate_mock):
            response = self.client.post(reverse("video-generate", args=[self.video.pk]))

        self.assertRedirects(response, reverse("video-detail", args=[self.video.pk]))
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Video generated successfully" in str(m) for m in messages))

        self.video.refresh_from_db()
        self.assertEqual(self.video.status, "ready")
        self.assertTrue(self.video.video_file.name)

    def test_generate_view_failure(self):
        self.client.login(username="creator", password="password")

        def _fail(video):
            video.status = "failed"
            video.error_message = "Generation error"
            video.save(update_fields=["status", "error_message"])
            raise VideoGenerationError("Generation error")

        with mock.patch("videos.views.generate_video_for_instance", side_effect=_fail):
            response = self.client.post(reverse("video-generate", args=[self.video.pk]))

        self.assertRedirects(response, reverse("video-detail", args=[self.video.pk]))
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Video generation failed" in str(m) for m in messages))

        self.video.refresh_from_db()
        self.assertEqual(self.video.status, "failed")
