import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from videos.models import AudioTrack, GeneratedVideo


class VideoListViewTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='tester', password='password')
        audio_file = SimpleUploadedFile('test.mp3', b'audio', content_type='audio/mpeg')
        AudioTrack.objects.create(title='Song', audio_file=audio_file)

    def test_video_list_requires_login(self):
        response = self.client.get(reverse('video-list'))
        self.assertEqual(response.status_code, 302)

    def test_video_list_authenticated(self):
        self.client.login(username='tester', password='password')
        response = self.client.get(reverse('video-list'))
        self.assertEqual(response.status_code, 200)


class GeneratedVideoCreateUpdateViewTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='creator', password='password')

    def test_create_video_redirects_to_list(self):
        self.client.login(username='creator', password='password')
        with tempfile.TemporaryDirectory() as tmpdir, override_settings(MEDIA_ROOT=tmpdir):
            audio_file = SimpleUploadedFile('test.mp3', b'audio', content_type='audio/mpeg')
            audio = AudioTrack.objects.create(title='Song', audio_file=audio_file)

            video_file = SimpleUploadedFile('video.mp4', b'video', content_type='video/mp4')
            response = self.client.post(
                reverse('video-create'),
                {
                    'audio_track': audio.id,
                    'title': 'Video Title',
                    'video_file': video_file,
                },
            )

            self.assertRedirects(response, reverse('video-list'))
            self.assertEqual(GeneratedVideo.objects.count(), 1)
            video = GeneratedVideo.objects.first()
            self.assertEqual(video.audio_track, audio)

    def test_update_video_redirects_to_list(self):
        self.client.login(username='creator', password='password')
        with tempfile.TemporaryDirectory() as tmpdir, override_settings(MEDIA_ROOT=tmpdir):
            audio_file = SimpleUploadedFile('test.mp3', b'audio', content_type='audio/mpeg')
            audio = AudioTrack.objects.create(title='Song', audio_file=audio_file)
            initial_video_file = SimpleUploadedFile('video.mp4', b'video', content_type='video/mp4')
            video = GeneratedVideo.objects.create(audio_track=audio, title='Video', video_file=initial_video_file)

            updated_video_file = SimpleUploadedFile('video2.mp4', b'new video', content_type='video/mp4')
            response = self.client.post(
                reverse('video-edit', args=[video.pk]),
                {
                    'audio_track': audio.id,
                    'title': 'Updated Title',
                    'video_file': updated_video_file,
                },
            )

            self.assertRedirects(response, reverse('video-list'))
            video.refresh_from_db()
            self.assertEqual(video.title, 'Updated Title')
