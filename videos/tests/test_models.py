import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from videos.models import ActivityLog, AudioTrack, GeneratedVideo, VideoProject


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class ModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester", password="secret")
        audio_file = SimpleUploadedFile("test.mp3", b"audio", content_type="audio/mpeg")
        self.audio = AudioTrack.objects.create(
            title="Sample Track",
            artist="Tester",
            audio_file=audio_file,
            lyrics="Sample lyrics",
            language="en",
            bpm=120,
        )

    def test_audio_track_fields_and_str(self):
        self.assertEqual(self.audio.title, "Sample Track")
        self.assertEqual(self.audio.artist, "Tester")
        self.assertEqual(self.audio.language, "en")
        self.assertEqual(self.audio.bpm, 120)
        self.assertEqual(str(self.audio), "Sample Track")
        self.assertTrue(self.audio.audio_file.name)

    def test_generated_video_defaults_and_str(self):
        video_file = SimpleUploadedFile("video.mp4", b"video", content_type="video/mp4")
        video = GeneratedVideo.objects.create(
            audio_track=self.audio,
            title="Video Title",
            description="Desc",
            video_file=video_file,
            thumbnail=None,
            resolution="1080p",
            aspect_ratio="16:9",
            mood="happy",
            tags="tag1,tag2",
            prompt_used="Prompt",
            model_name="model-x",
            seed=42,
            generation_time_ms=5000,
            generation_progress=50,
            generation_log="Started",
            error_code="",
        )

        self.assertEqual(video.status, "draft")
        self.assertTrue(video.is_active)
        self.assertEqual(video.generation_progress, 50)
        self.assertEqual(video.mood, "happy")
        self.assertTrue(video.video_file.name.endswith(".mp4"))
        self.assertEqual(str(video), "Video Title")

    def test_video_project_fields_and_str(self):
        video = GeneratedVideo.objects.create(audio_track=self.audio, title="Video A")
        project = VideoProject.objects.create(name="Project 1", description="Test project")
        project.videos.add(video)

        self.assertEqual(project.name, "Project 1")
        self.assertTrue(project.is_active)
        self.assertIn(video, project.videos.all())
        self.assertEqual(str(project), "Project 1")

    def test_activity_log_fields_and_str(self):
        log = ActivityLog.objects.create(
            user=self.user,
            action="create",
            object_type="GeneratedVideo",
            object_id=1,
            description="Created video",
        )
        self.assertEqual(log.action, "create")
        self.assertEqual(log.object_type, "GeneratedVideo")
        self.assertEqual(str(log), "create - GeneratedVideo (1)")
