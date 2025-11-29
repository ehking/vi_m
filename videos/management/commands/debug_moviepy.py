import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Debug MoviePy installation"

    def handle(self, *args, **options):
        import moviepy
        import moviepy.editor

        self.stdout.write(f"moviepy.version: {getattr(moviepy, 'version', 'unknown')}")
        self.stdout.write(f"moviepy.file: {getattr(moviepy, '__file__', 'unknown')}")
        self.stdout.write(f"sys.executable: {sys.executable}")
        self.stdout.write(f"sys.path: {sys.path}")
