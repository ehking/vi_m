from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from videos.models import AudioTrack, GeneratedVideo


class AudioTrackModelTest(TestCase):
    def test_create_audio_track_with_minimal_fields(self):
        audio_file = SimpleUploadedFile("test.mp3", b"audio", content_type="audio/mpeg")
        track = AudioTrack.objects.create(title="Test Song", audio_file=audio_file)

        self.assertEqual(str(track), "Test Song")
        self.assertEqual(track.artist, "")
        self.assertIsNotNone(track.created_at)


class GeneratedVideoModelTest(TestCase):
    def setUp(self):
        audio_file = SimpleUploadedFile("test.mp3", b"audio", content_type="audio/mpeg")
        self.audio = AudioTrack.objects.create(title="Test Song", audio_file=audio_file)

    def test_create_generated_video_defaults(self):
        video = GeneratedVideo.objects.create(audio_track=self.audio, title="Video Title")

        self.assertEqual(str(video), "Video Title")
        self.assertEqual(video.status, "draft")
        self.assertTrue(video.is_active)
        self.assertEqual(video.generation_progress, 0)
        self.assertEqual(video.error_message, "")
        self.assertFalse(video.video_file)
        self.assertIsNone(video.duration_seconds)
        self.assertIsNotNone(video.created_at)
        self.assertIsNotNone(video.updated_at)

    def test_generated_video_linked_to_audio(self):
        video = GeneratedVideo.objects.create(audio_track=self.audio, title="Linked Video")

        self.assertEqual(video.audio_track, self.audio)
        self.assertIn(video, self.audio.videos.all())
