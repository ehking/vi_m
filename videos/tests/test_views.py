from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from videos.models import AudioTrack


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
