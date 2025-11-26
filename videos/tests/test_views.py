import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from videos.models import AudioTrack, GeneratedVideo


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class VideoViewsTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='tester', password='password')
        self.client.login(username='tester', password='password')
        audio_file = SimpleUploadedFile('test.mp3', b'audio', content_type='audio/mpeg')
        self.audio = AudioTrack.objects.create(title='Song', audio_file=audio_file)

    def test_dashboard_context_counts(self):
        GeneratedVideo.objects.create(audio_track=self.audio, title='Ready', status='ready')
        GeneratedVideo.objects.create(audio_track=self.audio, title='Failed', status='failed', mood='sad')

        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_videos', response.context)
        self.assertEqual(response.context['total_videos'], 2)
        self.assertIn('total_audio', response.context)
        self.assertEqual(response.context['total_audio'], 1)

    def test_video_list_filters(self):
        GeneratedVideo.objects.create(audio_track=self.audio, title='Happy', status='ready', mood='happy', tags='fun')
        GeneratedVideo.objects.create(audio_track=self.audio, title='Sad Clip', status='failed', mood='sad', tags='drama')

        response = self.client.get(reverse('video-list'), {'status': 'ready'})
        self.assertContains(response, 'Happy')
        self.assertNotContains(response, 'Sad Clip')

        response = self.client.get(reverse('video-list'), {'mood': 'sad'})
        self.assertContains(response, 'Sad Clip')

        response = self.client.get(reverse('video-list'), {'search': 'fun'})
        self.assertContains(response, 'Happy')

    def test_video_detail_view(self):
        video = GeneratedVideo.objects.create(audio_track=self.audio, title='Detail Clip', status='ready')
        response = self.client.get(reverse('video-detail', args=[video.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['video'], video)

    def test_generate_ai_video_success(self):
        video = GeneratedVideo.objects.create(audio_track=self.audio, title='Generate Me')
        with patch('videos.views.generate_video_for_instance') as mock_generate:
            video.status = 'ready'
            mock_generate.return_value = video
            response = self.client.post(reverse('video-generate', args=[video.pk]))
        self.assertRedirects(response, reverse('video-detail', args=[video.pk]))
        self.assertTrue(mock_generate.called)

    def test_generate_ai_video_failure(self):
        video = GeneratedVideo.objects.create(audio_track=self.audio, title='Fail Me')
        with patch('videos.views.generate_video_for_instance', side_effect=Exception('boom')):
            response = self.client.post(reverse('video-generate', args=[video.pk]))
        self.assertRedirects(response, reverse('video-detail', args=[video.pk]))

    def test_create_and_update_video(self):
        video_file = SimpleUploadedFile('video.mp4', b'video', content_type='video/mp4')
        response = self.client.post(
            reverse('video-create'),
            {
                'audio_track': self.audio.id,
                'title': 'Video Title',
                'video_file': video_file,
            },
        )
        self.assertRedirects(response, reverse('video-list'))
        video = GeneratedVideo.objects.get(title='Video Title')

        updated_video_file = SimpleUploadedFile('video2.mp4', b'new video', content_type='video/mp4')
        response = self.client.post(
            reverse('video-edit', args=[video.pk]),
            {
                'audio_track': self.audio.id,
                'title': 'Updated Title',
                'video_file': updated_video_file,
            },
        )
        self.assertRedirects(response, reverse('video-list'))
        video.refresh_from_db()
        self.assertEqual(video.title, 'Updated Title')

    def test_audio_views(self):
        video = GeneratedVideo.objects.create(audio_track=self.audio, title='Linked Video')
        response = self.client.get(reverse('audio-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.audio.title)

        response = self.client.get(reverse('audio-detail', args=[self.audio.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, video.title)
