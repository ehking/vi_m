import os
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from videos.models import AudioTrack, GeneratedVideo


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class AudioAndVideoModelTests(TestCase):
    def setUp(self):
        self.audio_file = SimpleUploadedFile(
            "track.mp3", b"audio-bytes", content_type="audio/mpeg"
        )

    def test_create_audio_track(self):
        track = AudioTrack.objects.create(
            title="Test Song", artist="Tester", audio_file=self.audio_file
        )

        self.assertEqual(track.title, "Test Song")
        self.assertEqual(track.artist, "Tester")
        self.assertTrue(os.path.exists(track.audio_file.path))

    def test_create_generated_video(self):
        track = AudioTrack.objects.create(
            title="Video Song", artist="Artist", audio_file=self.audio_file
        )
        video_file = SimpleUploadedFile(
            "clip.mp4", b"video-bytes", content_type="video/mp4"
        )

        video = GeneratedVideo.objects.create(
            audio_track=track,
            title="Clip",
            video_file=video_file,
            status="ready",
            duration_seconds=12,
        )

        self.assertEqual(str(video), "Clip")
        self.assertEqual(video.audio_track, track)
        self.assertEqual(video.duration_seconds, 12)
        self.assertEqual(video.status, "ready")
        self.assertTrue(os.path.exists(video.video_file.path))
