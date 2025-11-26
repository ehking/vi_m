from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.contrib.auth import get_user_model

from videos.models import AudioTrack


class AudioTrackModelTest(TestCase):
    def test_create_audio_track(self):
        file = SimpleUploadedFile('test.mp3', b'audio', content_type='audio/mpeg')
        track = AudioTrack.objects.create(title='Test Song', artist='Tester', audio_file=file)
        self.assertEqual(str(track), 'Test Song')
        self.assertEqual(track.artist, 'Tester')
