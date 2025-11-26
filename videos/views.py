import os
from pathlib import Path
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Count, Q
from django.db.utils import OperationalError
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
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


def _activity_user(request):
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        return user
    return None


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
            context['total_videos'] = videos.count()
            context['status_counts'] = list(videos.values('status').annotate(total=Count('id')))
            context['mood_counts'] = list(videos.values('mood').annotate(total=Count('id')))
            context['total_audio'] = AudioTrack.objects.count()
            context['total_projects'] = VideoProject.objects.count()
            context['recent_videos'] = list(videos.order_by('-created_at')[:5])
        except OperationalError as exc:
            messages.error(
                self.request,
                "Database schema is out of date. Please run 'python manage.py migrate' to create new"
                f" columns (error: {exc}).",
            )
            context.update(
                total_videos=0,
                status_counts=[],
                mood_counts=[],
                total_audio=0,
                total_projects=0,
                recent_videos=[],
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
            # Trigger a lightweight query so schema issues (e.g., missing columns) surface here
            # and can be handled gracefully instead of exploding during template rendering.
            queryset.exists()
        except OperationalError as exc:
            messages.error(
                self.request,
                "Database schema is out of date. Please run 'python manage.py migrate' to create new"
                f" columns (error: {exc}).",
            )
            return GeneratedVideo.objects.none()
        return queryset



class GeneratedVideoDetailView(DetailView):
    model = GeneratedVideo
    template_name = 'videos/video_detail.html'
    context_object_name = 'video'


@require_POST
def video_generate(request, pk):
    video = get_object_or_404(GeneratedVideo, pk=pk)
    redirect_url = redirect('video-detail', pk=pk)

    video.status = 'processing'
    video.error_message = ''
    video.generation_progress = 0
    video.save(update_fields=['status', 'error_message', 'generation_progress', 'updated_at'])

    try:
        audio_file = video.audio_track.audio_file
        if not audio_file:
            raise ValueError('Audio file is missing for this track.')
        if not hasattr(audio_file, 'path') or not os.path.exists(audio_file.path):
            raise ValueError('Audio file path is invalid or the file does not exist.')

        from moviepy.editor import AudioFileClip, ColorClip, CompositeVideoClip, ImageClip
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np

        audio_path = Path(audio_file.path)
        output_dir = Path(settings.MEDIA_ROOT) / 'videos'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_name = f'generated_{video.pk}.mp4'
        output_path = output_dir / output_name

        with AudioFileClip(str(audio_path)) as audio_clip:
            duration = audio_clip.duration or 0
            duration_seconds = int(duration)

            background = ColorClip(size=(1280, 720), color=(0, 0, 0), duration=duration)

            text_lines = [video.title or video.audio_track.title]
            first_line = ''
            if video.audio_track.lyrics:
                first_line = video.audio_track.lyrics.strip().splitlines()[0]
            if first_line:
                text_lines.append(first_line)
            text_content = "\n".join(filter(None, text_lines)) or "Generated Video"

            img = Image.new('RGBA', (1280, 720), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            font = ImageFont.load_default()
            bbox = draw.multiline_textbbox((0, 0), text_content, font=font, align='center')
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            position = ((img.width - text_width) // 2, (img.height - text_height) // 2)
            draw.multiline_text(position, text_content, font=font, fill=(255, 255, 255, 230), align='center')

            text_clip = ImageClip(np.array(img)).set_duration(duration)

            composite = CompositeVideoClip([background, text_clip]).set_audio(audio_clip)
            composite.write_videofile(
                str(output_path),
                fps=24,
                codec='libx264',
                audio_codec='aac',
                verbose=False,
                logger=None,
            )

            composite.close()
            background.close()
            text_clip.close()

        video.video_file.name = f'videos/{output_name}'
        video.duration_seconds = duration_seconds
        video.file_size_bytes = os.path.getsize(output_path) if output_path.exists() else None
        video.generation_progress = 100
        video.status = 'ready'
        video.save(update_fields=[
            'video_file',
            'duration_seconds',
            'file_size_bytes',
            'generation_progress',
            'status',
            'updated_at',
        ])

        ActivityLog.objects.create(
            user=_activity_user(request),
            action='generate_video',
            object_type='GeneratedVideo',
            object_id=video.id,
            description=f"Generated video {video.title}",
        )
        messages.success(request, 'Video generated successfully.')
    except Exception as exc:
        video.status = 'failed'
        video.error_message = str(exc)
        video.generation_progress = 0
        video.save(update_fields=['status', 'error_message', 'generation_progress', 'updated_at'])
        messages.error(request, f'Failed to generate video: {exc}')

    return redirect_url


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
