from django.conf import settings
from django.db import models


class AudioTrack(models.Model):
    title = models.CharField(max_length=255)
    artist = models.CharField(max_length=255, blank=True)
    audio_file = models.FileField(upload_to="audio/")
    lyrics = models.TextField(blank=True)
    language = models.CharField(max_length=10, blank=True)
    bpm = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class GeneratedVideo(models.Model):
    MOOD_CHOICES = [
        ("sad", "Sad"),
        ("happy", "Happy"),
        ("epic", "Epic"),
        ("romantic", "Romantic"),
        ("dark", "Dark"),
        ("chill", "Chill"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("ready", "Ready"),
        ("failed", "Failed"),
        ("archived", "Archived"),
    ]

    audio_track = models.ForeignKey(AudioTrack, related_name="videos", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    video_file = models.FileField(upload_to="videos/")
    thumbnail = models.ImageField(upload_to="thumbnails/", blank=True, null=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    resolution = models.CharField(max_length=50, blank=True)
    aspect_ratio = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    error_message = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    tags = models.TextField(blank=True)
    mood = models.CharField(max_length=20, blank=True, choices=MOOD_CHOICES)
    prompt_used = models.TextField(blank=True)
    model_name = models.CharField(max_length=100, blank=True)
    generation_time_ms = models.IntegerField(null=True, blank=True)
    seed = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class VideoProject(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    videos = models.ManyToManyField(GeneratedVideo, related_name="projects", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class ActivityLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100)
    object_id = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} - {self.object_type} ({self.object_id})"
