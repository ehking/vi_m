import os
import shutil
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from videos.models import AudioTrack, BackgroundVideo, GeneratedVideo
from videos.services.video_generation import generate_lyric_video_for_instance


class DummyClip:
    def __init__(self, duration=1):
        self.duration = duration

    def resize(self, _size):
        return self

    def set_duration(self, duration):
        self.duration = duration
        return self

    def set_position(self, _pos):
        return self

    def set_audio(self, _audio):
        return self

    def write_videofile(self, path, **_kwargs):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"video-data")
        return path

    def close(self):
        pass


class DummyComposite(DummyClip):
    pass


class LyricVideoGenerationTest(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.temp_dir)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_lyric_video_sets_file_and_status(self):
        audio_file = SimpleUploadedFile("audio.mp3", b"audio-bytes", content_type="audio/mpeg")
        audio = AudioTrack.objects.create(title="Song", audio_file=audio_file, lyrics="hello world")
        background_file = SimpleUploadedFile("bg.mp4", b"bg-bytes", content_type="video/mp4")
        background = BackgroundVideo.objects.create(title="BG", video_file=background_file)
        video = GeneratedVideo.objects.create(
            audio_track=audio, title="Lyric", background_video=background
        )

        dummy_audio_clip = DummyClip(duration=2)
        dummy_bg_clip = DummyClip(duration=3)
        dummy_text_clip = DummyClip(duration=2)

        fake_editor = types.SimpleNamespace(
            AudioFileClip=lambda *_args, **_kwargs: dummy_audio_clip,
            VideoFileClip=lambda *_args, **_kwargs: dummy_bg_clip,
            TextClip=lambda *_args, **_kwargs: dummy_text_clip,
            CompositeVideoClip=lambda *_args, **_kwargs: DummyComposite(duration=2),
        )

        with patch.dict(
            "sys.modules",
            {
                "moviepy": types.SimpleNamespace(editor=fake_editor),
                "moviepy.editor": fake_editor,
            },
        ):
            generate_lyric_video_for_instance(video)

        video.refresh_from_db()
        self.assertEqual(video.status, "ready")
        self.assertTrue(video.video_file.name)
        output_path = os.path.join(settings.MEDIA_ROOT, video.video_file.name)
        self.assertTrue(os.path.exists(output_path))
        self.assertGreaterEqual(video.duration_seconds, 1)
