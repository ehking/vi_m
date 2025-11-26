import os
from datetime import datetime

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from videos.models import AudioTrack, GeneratedVideo

SAMPLE_AUDIO_BYTES = b"ID3\x04\x00\x00\x00\x00\x00\x21'Demo MP3 data"
SAMPLE_VIDEO_BYTES = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42mp41demo video content"


class Command(BaseCommand):
    help = "Create a sample audio track and generated video for demos or local testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--title",
            default="Sample Video",
            help="Title to use for the generated sample video.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recreate sample files even if records already exist.",
        )

    def handle(self, *args, **options):
        title = options["title"]
        force = options["force"]

        audio = self._get_or_create_audio(force=force)
        video = self._get_or_create_video(audio, title=title, force=force)
        self._update_file_metadata(video)

        self.stdout.write(
            self.style.SUCCESS(
                f"Sample video '{video.title}' ready with audio track '{audio.title}'."
            )
        )

    def _get_or_create_audio(self, force: bool) -> AudioTrack:
        audio, created = AudioTrack.objects.get_or_create(
            title="Sample Audio Track",
            defaults={
                "artist": "System",
                "audio_file": ContentFile(SAMPLE_AUDIO_BYTES, name="sample.mp3"),
                "lyrics": "Sample lyrics for demo playback",
                "language": "en",
                "bpm": 120,
            },
        )

        if force or not audio.audio_file:
            audio.audio_file.save("sample.mp3", ContentFile(SAMPLE_AUDIO_BYTES), save=True)
        return audio

    def _get_or_create_video(self, audio: AudioTrack, title: str, force: bool) -> GeneratedVideo:
        now = datetime.utcnow().isoformat()
        defaults = {
            "audio_track": audio,
            "description": "Sample generated video for showcasing the dashboard.",
            "video_file": ContentFile(SAMPLE_VIDEO_BYTES, name="sample.mp4"),
            "status": "ready",
            "mood": "happy",
            "tags": "sample,demo",
            "prompt_used": "Sample prompt",
            "model_name": "demo-generator",
            "generation_progress": 100,
            "generation_log": f"Generated sample video at {now}",
        }

        video, created = GeneratedVideo.objects.get_or_create(title=title, defaults=defaults)

        if force or not video.video_file:
            video.video_file.save("sample.mp4", ContentFile(SAMPLE_VIDEO_BYTES), save=False)
            video.status = "ready"
            video.generation_progress = 100
            video.generation_log = f"Regenerated sample video at {now}"
            video.save()

        if not video.audio_track_id:
            video.audio_track = audio
            video.save(update_fields=["audio_track"])

        return video

    def _update_file_metadata(self, video: GeneratedVideo) -> None:
        video_file = video.video_file
        if video_file and hasattr(video_file, "path") and os.path.exists(video_file.path):
            video.file_size_bytes = os.path.getsize(video_file.path)
            if not video.duration_seconds:
                video.duration_seconds = 0
            if not video.resolution:
                video.resolution = ""
            if not video.aspect_ratio:
                video.aspect_ratio = ""
            video.save()
