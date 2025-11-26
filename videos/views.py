import logging
import os
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.files.base import ContentFile
from django.db.models import Count, Q
from django.db.utils import OperationalError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)
from django.views.generic.edit import FormMixin

from .forms import (
    AudioTrackForm,
    GeneratedVideoForm,
    GeneratedVideoStatusForm,
    VideoProjectForm,
)
from .models import (
    ActivityLog,
    AudioTrack,
    GeneratedVideo,
    VideoGenerationLog,
    VideoProject,
)
from .services.video_generation import VideoGenerationError, generate_video_for_instance

logger = logging.getLogger(__name__)
STATUS_BADGE_CLASSES = GeneratedVideo.STATUS_BADGE_CLASSES


def _status_summary():
    try:
        status_totals = GeneratedVideo.objects.values("status").annotate(total=Count("id"))
    except OperationalError:
        return []

    labels = dict(GeneratedVideo.STATUS_CHOICES)
    return [
        {
            "key": row["status"],
            "label": labels.get(row["status"], row["status"].title()),
            "badge": STATUS_BADGE_CLASSES.get(row["status"], "secondary"),
            "total": row["total"],
        }
        for row in status_totals
    ]

STATUS_BADGE_CLASSES = GeneratedVideo.STATUS_BADGE_CLASSES


def _activity_user(request):
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        return user
    return None


def _status_summary():
    status_counts = GeneratedVideo.objects.values("status").annotate(total=Count("id"))
    status_map = {item["status"]: item["total"] for item in status_counts}
    status_order = ["ready", "processing", "pending", "failed", "draft", "archived"]
    return [
        {
            "key": status,
            "label": dict(GeneratedVideo.STATUS_CHOICES).get(status, status.title()),
            "count": status_map.get(status, 0),
        }
        for status in status_order
    ]


class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to perform this action.")
        return redirect('dashboard')


class DashboardView(TemplateView):
    template_name = 'videos/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            videos = GeneratedVideo.objects.all()
            status_counts = _status_summary()
            status_map = {item["key"]: item["total"] for item in status_counts}
            context['status_ready'] = status_map.get('ready', 0)
            context['status_classes'] = STATUS_BADGE_CLASSES
            context['total_videos'] = videos.count()
            context['status_counts'] = status_counts
            context['mood_counts'] = list(videos.values('mood').annotate(total=Count('id')))
            context['total_audio'] = AudioTrack.objects.count()
            context['total_projects'] = VideoProject.objects.count()
            context['recent_videos'] = list(videos.select_related('audio_track').order_by('-created_at')[:5])
        except OperationalError as exc:
            messages.error(
                self.request,
                "Database schema is out of date. Please run 'python manage.py migrate' to create new"
                f" columns (error: {exc}).",
            )
            context.update(
                total_videos=0,
                status_summary=[],
                mood_counts=[],
                total_audio=0,
                total_projects=0,
                recent_videos=[],
                status_ready=0,
            )
        return context


class GeneratedVideoListView(ListView):
    model = GeneratedVideo
    template_name = 'videos/video_list.html'
    context_object_name = 'videos'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('audio_track')
        status = self.request.GET.get('status')
        mood = self.request.GET.get('mood')
        search = self.request.GET.get('search')
        if status:
            queryset = queryset.filter(status=status)
        if mood:
            queryset = queryset.filter(mood=mood)
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(tags__icontains=search))
        queryset = queryset.order_by('-created_at')
        try:
            queryset.exists()
        except OperationalError as exc:
            messages.error(
                self.request,
                "Database schema is out of date. Please run 'python manage.py migrate' to create new"
                f" columns (error: {exc}).",
            )
            return GeneratedVideo.objects.none()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_counts'] = _status_summary()
        return context


class GeneratedVideoDetailView(FormMixin, DetailView):
    model = GeneratedVideo
    template_name = 'videos/video_detail.html'
    context_object_name = 'video'
    form_class = GeneratedVideoStatusForm

    def get_success_url(self):
        return reverse('video-detail', kwargs={'pk': self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.get_object()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = kwargs.get('form') or context.get('form') or self.get_form()
        tags = []
        if self.object.tags:
            tags = [tag.strip() for tag in self.object.tags.split(',') if tag.strip()]
        context['tags'] = tags
        context['status_classes'] = STATUS_BADGE_CLASSES
        context['generation_logs'] = list(
            self.object.generation_logs.all().order_by('-created_at')[:100]
        )
        context['has_debug_access'] = self.request.user.is_staff
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            form.save()
            ActivityLog.objects.create(
                user=_activity_user(request),
                action='update_video_status',
                object_type='GeneratedVideo',
                object_id=self.object.id,
                description=f"Updated status details for video {self.object.title}",
            )
            messages.success(request, 'Video status updated successfully.')
            return redirect(self.get_success_url())
        context = self.get_context_data(form=form)
        return self.render_to_response(context)


def generate_video_for_audio(audio_track: AudioTrack):
    """Create a placeholder video file for the given audio track.

    This helper is intentionally simple so it can be mocked in tests or swapped
    for a real MoviePy-based implementation later.
    """

    # In a real system we would render visuals synchronized to the audio.
    # For now, return deterministic bytes and a short duration.
    return b"DEMO_MP4_DATA", 5


class VideoGenerationDebugListView(TemplateView):
    template_name = 'videos/debug_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['recent_failures'] = list(
            VideoGenerationLog.objects.select_related('video')
            .filter(status='failed')
            .order_by('-created_at')[:20]
        )
        context['recent_activity'] = list(
            VideoGenerationLog.objects.select_related('video')
            .order_by('-created_at')[:20]
        )
        return context


class GenerateVideoView(View):
    def post(self, request, pk):
        video = get_object_or_404(GeneratedVideo, pk=pk)
        if video.status == "processing":
            messages.info(request, "Video generation already in progress.")
            return redirect('video-detail', pk=video.pk)

        try:
            generate_video_for_instance(video)
        except VideoGenerationError as exc:
            logger.warning("Video generation failed for video %s: %s", video.pk, exc)
            messages.error(request, f"Failed to generate video: {exc}")
            return redirect('video-detail', pk=pk)

        ActivityLog.objects.create(
            user=_activity_user(request),
            action='generate_video',
            object_type='GeneratedVideo',
            object_id=video.id,
            description=f"Generated video {video.title}",
        )
        if video.status == "ready":
            messages.success(request, 'AI video generated successfully.')
        else:
            messages.error(request, video.error_message or "Video generation failed.")
        return redirect('video-detail', pk=pk)


class VideoGenerationDebugListView(StaffRequiredMixin, ListView):
    model = VideoGenerationLog
    template_name = "videos/debug_list.html"
    context_object_name = "generation_logs"
    paginate_by = 50


class AudioGenerateVideoView(View):
    def post(self, request, pk):
        audio_track = get_object_or_404(AudioTrack, pk=pk)
        video = GeneratedVideo.objects.create(audio_track=audio_track, title=audio_track.title)
        try:
            video_bytes, duration_seconds = generate_video_for_audio(audio_track)
            filename = f"generated_audio_{audio_track.pk}.mp4"
            video.video_file.save(filename, ContentFile(video_bytes), save=False)
            video.duration_seconds = duration_seconds
            video.status = "ready"
            video.error_message = ""
            video.save(update_fields=["video_file", "duration_seconds", "status", "error_message"])
            messages.success(request, "Video generated successfully.")
        except Exception as exc:  # pragma: no cover - surface errors to user
            video.status = "failed"
            video.error_message = str(exc)
            video.save(update_fields=["status", "error_message"])
            messages.error(request, f"Video generation failed: {exc}")

        return redirect('audio-detail', pk=audio_track.pk)


class GeneratedVideoCreateView(CreateView):
    model = GeneratedVideo
    form_class = GeneratedVideoForm
    template_name = 'videos/video_form.html'
    success_url = reverse_lazy('video-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        self._update_file_metadata()
        ActivityLog.objects.create(
            user=_activity_user(self.request),
            action='create_video',
            object_type='GeneratedVideo',
            object_id=self.object.id,
            description=f"Created video {self.object.title}",
        )
        messages.success(self.request, 'Video created successfully.')
        return response

    def _update_file_metadata(self):
        video_file = self.object.video_file
        if video_file and hasattr(video_file, 'path') and os.path.exists(video_file.path):
            self.object.file_size_bytes = os.path.getsize(video_file.path)
            if not self.object.duration_seconds:
                self.object.duration_seconds = 0
            if not self.object.resolution:
                self.object.resolution = ''
            if not self.object.aspect_ratio:
                self.object.aspect_ratio = ''
            self.object.save()


class GeneratedVideoUpdateView(UpdateView):
    model = GeneratedVideo
    form_class = GeneratedVideoForm
    template_name = 'videos/video_form.html'
    success_url = reverse_lazy('video-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        self._update_file_metadata()
        ActivityLog.objects.create(
            user=_activity_user(self.request),
            action='update_video',
            object_type='GeneratedVideo',
            object_id=self.object.id,
            description=f"Updated video {self.object.title}",
        )
        messages.success(self.request, 'Video updated successfully.')
        return response

    def _update_file_metadata(self):
        video_file = self.object.video_file
        if video_file and hasattr(video_file, 'path') and os.path.exists(video_file.path):
            self.object.file_size_bytes = os.path.getsize(video_file.path)
            if not self.object.duration_seconds:
                self.object.duration_seconds = 0
            if not self.object.resolution:
                self.object.resolution = ''
            if not self.object.aspect_ratio:
                self.object.aspect_ratio = ''
            self.object.save()


class GeneratedVideoDeleteView(StaffRequiredMixin, DeleteView):
    model = GeneratedVideo
    template_name = 'videos/video_confirm_delete.html'
    success_url = reverse_lazy('video-list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        ActivityLog.objects.create(
            user=_activity_user(request),
            action='delete_video',
            object_type='GeneratedVideo',
            object_id=self.object.id,
            description=f"Deleted video {self.object.title}",
        )
        messages.success(request, 'Video deleted successfully.')
        return super().delete(request, *args, **kwargs)


class AudioTrackListView(ListView):
    model = AudioTrack
    template_name = 'videos/audio_list.html'
    context_object_name = 'audio_tracks'
    paginate_by = 10


class AudioTrackDetailView(DetailView):
    model = AudioTrack
    template_name = 'videos/audio_detail.html'
    context_object_name = 'audio'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["related_videos"] = self.object.videos.order_by("-created_at")
        return context


class AudioTrackCreateView(CreateView):
    model = AudioTrack
    form_class = AudioTrackForm
    template_name = 'videos/audio_form.html'
    success_url = reverse_lazy('audio-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        ActivityLog.objects.create(
            user=_activity_user(self.request),
            action='create_audio',
            object_type='AudioTrack',
            object_id=self.object.id,
            description=f"Created audio track {self.object.title}",
        )
        messages.success(self.request, 'Audio track created successfully.')
        return response


class AudioTrackUpdateView(UpdateView):
    model = AudioTrack
    form_class = AudioTrackForm
    template_name = 'videos/audio_form.html'
    success_url = reverse_lazy('audio-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        ActivityLog.objects.create(
            user=_activity_user(self.request),
            action='update_audio',
            object_type='AudioTrack',
            object_id=self.object.id,
            description=f"Updated audio track {self.object.title}",
        )
        messages.success(self.request, 'Audio track updated successfully.')
        return response


class AudioTrackDeleteView(StaffRequiredMixin, DeleteView):
    model = AudioTrack
    template_name = 'videos/audio_confirm_delete.html'
    success_url = reverse_lazy('audio-list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        ActivityLog.objects.create(
            user=_activity_user(request),
            action='delete_audio',
            object_type='AudioTrack',
            object_id=self.object.id,
            description=f"Deleted audio track {self.object.title}",
        )
        messages.success(request, 'Audio track deleted successfully.')
        return super().delete(request, *args, **kwargs)


class VideoProjectListView(ListView):
    model = VideoProject
    template_name = 'videos/project_list.html'
    context_object_name = 'projects'
    paginate_by = 10


class VideoProjectDetailView(DetailView):
    model = VideoProject
    template_name = 'videos/project_detail.html'
    context_object_name = 'project'


class VideoProjectCreateView(CreateView):
    model = VideoProject
    form_class = VideoProjectForm
    template_name = 'videos/project_form.html'
    success_url = reverse_lazy('project-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        ActivityLog.objects.create(
            user=_activity_user(self.request),
            action='create_project',
            object_type='VideoProject',
            object_id=self.object.id,
            description=f"Created project {self.object.name}",
        )
        messages.success(self.request, 'Project created successfully.')
        return response


class VideoProjectUpdateView(UpdateView):
    model = VideoProject
    form_class = VideoProjectForm
    template_name = 'videos/project_form.html'
    success_url = reverse_lazy('project-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        ActivityLog.objects.create(
            user=_activity_user(self.request),
            action='update_project',
            object_type='VideoProject',
            object_id=self.object.id,
            description=f"Updated project {self.object.name}",
        )
        messages.success(self.request, 'Project updated successfully.')
        return response


class VideoProjectDeleteView(StaffRequiredMixin, DeleteView):
    model = VideoProject
    template_name = 'videos/project_confirm_delete.html'
    success_url = reverse_lazy('project-list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        ActivityLog.objects.create(
            user=_activity_user(request),
            action='delete_project',
            object_type='VideoProject',
            object_id=self.object.id,
            description=f"Deleted project {self.object.name}",
        )
        messages.success(request, 'Project deleted successfully.')
        return super().delete(request, *args, **kwargs)
