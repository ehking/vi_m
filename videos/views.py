import os
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from .forms import AudioTrackForm, GeneratedVideoForm, VideoProjectForm
from .models import ActivityLog, AudioTrack, GeneratedVideo, VideoProject


class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to perform this action.")
        return redirect('dashboard')


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'videos/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        videos = GeneratedVideo.objects.all()
        context['total_videos'] = videos.count()
        context['status_counts'] = videos.values('status').annotate(total=Count('id'))
        context['mood_counts'] = videos.values('mood').annotate(total=Count('id'))
        context['total_audio'] = AudioTrack.objects.count()
        context['total_projects'] = VideoProject.objects.count()
        context['recent_videos'] = videos.order_by('-created_at')[:5]
        return context


class GeneratedVideoListView(LoginRequiredMixin, ListView):
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
        return queryset.order_by('-created_at')


class GeneratedVideoDetailView(LoginRequiredMixin, DetailView):
    model = GeneratedVideo
    template_name = 'videos/video_detail.html'
    context_object_name = 'video'


class GeneratedVideoCreateView(LoginRequiredMixin, CreateView):
    model = GeneratedVideo
    form_class = GeneratedVideoForm
    template_name = 'videos/video_form.html'
    success_url = reverse_lazy('video-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        self._update_file_metadata()
        ActivityLog.objects.create(
            user=self.request.user,
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


class GeneratedVideoUpdateView(LoginRequiredMixin, UpdateView):
    model = GeneratedVideo
    form_class = GeneratedVideoForm
    template_name = 'videos/video_form.html'
    success_url = reverse_lazy('video-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        self._update_file_metadata()
        ActivityLog.objects.create(
            user=self.request.user,
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
            user=request.user,
            action='delete_video',
            object_type='GeneratedVideo',
            object_id=self.object.id,
            description=f"Deleted video {self.object.title}",
        )
        messages.success(request, 'Video deleted successfully.')
        return super().delete(request, *args, **kwargs)


class AudioTrackListView(LoginRequiredMixin, ListView):
    model = AudioTrack
    template_name = 'videos/audio_list.html'
    context_object_name = 'audio_tracks'
    paginate_by = 10


class AudioTrackDetailView(LoginRequiredMixin, DetailView):
    model = AudioTrack
    template_name = 'videos/audio_detail.html'
    context_object_name = 'audio'


class AudioTrackCreateView(LoginRequiredMixin, CreateView):
    model = AudioTrack
    form_class = AudioTrackForm
    template_name = 'videos/audio_form.html'
    success_url = reverse_lazy('audio-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        ActivityLog.objects.create(
            user=self.request.user,
            action='create_audio',
            object_type='AudioTrack',
            object_id=self.object.id,
            description=f"Created audio track {self.object.title}",
        )
        messages.success(self.request, 'Audio track created successfully.')
        return response


class AudioTrackUpdateView(LoginRequiredMixin, UpdateView):
    model = AudioTrack
    form_class = AudioTrackForm
    template_name = 'videos/audio_form.html'
    success_url = reverse_lazy('audio-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        ActivityLog.objects.create(
            user=self.request.user,
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
            user=request.user,
            action='delete_audio',
            object_type='AudioTrack',
            object_id=self.object.id,
            description=f"Deleted audio track {self.object.title}",
        )
        messages.success(request, 'Audio track deleted successfully.')
        return super().delete(request, *args, **kwargs)


class VideoProjectListView(LoginRequiredMixin, ListView):
    model = VideoProject
    template_name = 'videos/project_list.html'
    context_object_name = 'projects'
    paginate_by = 10


class VideoProjectDetailView(LoginRequiredMixin, DetailView):
    model = VideoProject
    template_name = 'videos/project_detail.html'
    context_object_name = 'project'


class VideoProjectCreateView(LoginRequiredMixin, CreateView):
    model = VideoProject
    form_class = VideoProjectForm
    template_name = 'videos/project_form.html'
    success_url = reverse_lazy('project-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        ActivityLog.objects.create(
            user=self.request.user,
            action='create_project',
            object_type='VideoProject',
            object_id=self.object.id,
            description=f"Created project {self.object.name}",
        )
        messages.success(self.request, 'Project created successfully.')
        return response


class VideoProjectUpdateView(LoginRequiredMixin, UpdateView):
    model = VideoProject
    form_class = VideoProjectForm
    template_name = 'videos/project_form.html'
    success_url = reverse_lazy('project-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        ActivityLog.objects.create(
            user=self.request.user,
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
            user=request.user,
            action='delete_project',
            object_type='VideoProject',
            object_id=self.object.id,
            description=f"Deleted project {self.object.name}",
        )
        messages.success(request, 'Project deleted successfully.')
        return super().delete(request, *args, **kwargs)
