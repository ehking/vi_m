from django.contrib import admin
from django.utils.html import format_html

from .models import ActivityLog, AudioTrack, GeneratedVideo, VideoProject


class GeneratedVideoInline(admin.TabularInline):
    model = GeneratedVideo
    extra = 0
    fields = ("title", "status", "mood", "created_at")
    readonly_fields = ("created_at",)


@admin.register(AudioTrack)
class AudioTrackAdmin(admin.ModelAdmin):
    list_display = ("title", "artist", "language", "created_at")
    search_fields = ("title", "artist")
    list_filter = ("language", "created_at")
    inlines = [GeneratedVideoInline]


@admin.register(GeneratedVideo)
class GeneratedVideoAdmin(admin.ModelAdmin):
    list_display = (
        "thumbnail_preview",
        "title",
        "audio_track",
        "status",
        "generation_progress",
        "mood",
        "created_at",
        "is_active",
    )
    list_filter = ("status", "mood", "is_active", "created_at")
    search_fields = ("title", "audio_track__title", "tags", "model_name", "error_code")
    readonly_fields = (
        "created_at",
        "updated_at",
        "file_size_bytes",
        "duration_seconds",
        "thumbnail_preview",
    )

    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" style="height:50px;" />', obj.thumbnail.url)
        return "-"

    thumbnail_preview.short_description = "Thumbnail"


@admin.register(VideoProject)
class VideoProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at", "is_active")
    filter_horizontal = ("videos",)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("action", "object_type", "object_id", "user", "created_at")
    list_filter = ("action", "object_type", "created_at")
    search_fields = ("description",)
    readonly_fields = ("action", "object_type", "object_id", "user", "description", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
