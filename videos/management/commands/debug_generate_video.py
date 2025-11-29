import os
import traceback

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from videos.models import GeneratedVideo
from videos.services.video_generation import generate_video_for_instance


class Command(BaseCommand):
    help = "Generate a video with detailed logging for debugging MoviePy/ffmpeg failures."

    def add_arguments(self, parser):
        parser.add_argument(
            "--video-id",
            type=int,
            help="ID of a GeneratedVideo to process. If omitted, uses the latest with audio and background.",
        )

    def handle(self, *args, **options):
        video_id = options.get("video_id")

        if video_id:
            try:
                video = GeneratedVideo.objects.get(pk=video_id)
            except GeneratedVideo.DoesNotExist as exc:  # pragma: no cover - defensive
                raise CommandError(f"GeneratedVideo with id {video_id} does not exist") from exc
        else:
            video = (
                GeneratedVideo.objects.filter(background_video__isnull=False, audio_track__isnull=False)
                .order_by("-created_at")
                .first()
            )
            if not video:
                raise CommandError(
                    "No GeneratedVideo instances with both background and audio were found. "
                    "Please create one via the admin or UI first."
                )

        self.stdout.write(f"Processing GeneratedVideo id={video.id} title='{video.title}'")

        bg_field = getattr(getattr(video, "background_video", None), "video_file", None)
        audio_field = getattr(getattr(video, "audio_track", None), "audio_file", None)
        bg_path = os.path.join(settings.MEDIA_ROOT, bg_field.name) if bg_field else None
        audio_path = os.path.join(settings.MEDIA_ROOT, audio_field.name) if audio_field else None

        if bg_path:
            self.stdout.write(f"Background video path: {bg_path}")
        if audio_path:
            self.stdout.write(f"Audio track path: {audio_path}")

        try:
            generate_video_for_instance(video)
        except Exception as exc:  # pragma: no cover - surface stack traces
            self.stderr.write(self.style.ERROR(f"Video generation failed: {exc}"))
            traceback.print_exc()
            raise CommandError("Video generation failed") from exc

        self.stdout.write(self.style.SUCCESS("Video generated successfully."))
