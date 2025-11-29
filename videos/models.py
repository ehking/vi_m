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
    video_file = models.FileField(
        upload_to="videos/",
        blank=True,
        null=True,
        help_text="Optional. Leave blank to generate the video from the audio track.",
    )
    thumbnail = models.ImageField(upload_to="thumbnails/", blank=True, null=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    resolution = models.CharField(max_length=50, blank=True)
    aspect_ratio = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    STATUS_BADGE_CLASSES = {
        "draft": "secondary",
        "pending": "info",
        "processing": "warning",
        "ready": "success",
        "failed": "danger",
        "archived": "secondary",
    }
    error_message = models.TextField(blank=True)
    current_stage = models.CharField(max_length=100, blank=True)
    last_error_message = models.TextField(blank=True)
    last_error_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    tags = models.TextField(blank=True)
    mood = models.CharField(max_length=20, blank=True, choices=MOOD_CHOICES)
    prompt_used = models.TextField(blank=True)
    model_name = models.CharField(max_length=100, blank=True)
    generation_time_ms = models.IntegerField(null=True, blank=True)
    generation_progress = models.IntegerField(null=True, blank=True)
    generation_log = models.TextField(blank=True)
    error_code = models.CharField(max_length=100, blank=True)
    seed = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def status_badge_class(self):
        return self.STATUS_BADGE_CLASSES.get(self.status, "secondary")


class VideoGenerationLog(models.Model):
    STATUS_CHOICES = [
        ("started", "Started"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("info", "Info"),
    ]

    video = models.ForeignKey(
        GeneratedVideo,
        related_name="generation_logs",
        on_delete=models.CASCADE,
    )
    stage = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    message = models.TextField(blank=True)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.video_id} - {self.stage} ({self.status})"


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


class AIProviderConfig(models.Model):
    name = models.CharField(max_length=255, unique=True)
    base_url = models.URLField()
    endpoint_path = models.CharField(max_length=255)
    api_key = models.CharField(max_length=255, blank=True)
    extra_headers = models.TextField(blank=True, help_text="Optional JSON for additional headers")
    extra_payload = models.TextField(blank=True, help_text="Optional JSON merged into request payload")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AIVideoJob(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    provider = models.ForeignKey(AIProviderConfig, on_delete=models.CASCADE, related_name="jobs")
    audio_track = models.ForeignKey(AudioTrack, on_delete=models.CASCADE, related_name="ai_jobs")
    background_video = models.ForeignKey(
        GeneratedVideo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_background_jobs",
    )
    prompt = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    request_payload = models.TextField(blank=True)
    response_raw = models.TextField(blank=True)
    video = models.ForeignKey(
        GeneratedVideo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_jobs",
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.provider.name} job #{self.pk}"

    @property
    def is_finished(self):
        return self.status in {self.STATUS_SUCCESS, self.STATUS_FAILED}
