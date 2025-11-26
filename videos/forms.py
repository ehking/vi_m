from django import forms
from .models import AudioTrack, GeneratedVideo, VideoProject


class AudioTrackForm(forms.ModelForm):
    class Meta:
        model = AudioTrack
        fields = [
            'title',
            'artist',
            'audio_file',
            'lyrics',
            'language',
            'bpm',
        ]


class GeneratedVideoForm(forms.ModelForm):
    class Meta:
        model = GeneratedVideo
        fields = [
            'audio_track',
            'title',
            'description',
            'video_file',
            'thumbnail',
            'mood',
            'tags',
            'status',
            'prompt_used',
            'model_name',
            'seed',
            'generation_time_ms',
            'resolution',
            'aspect_ratio',
            'is_active',
        ]


class VideoProjectForm(forms.ModelForm):
    class Meta:
        model = VideoProject
        fields = [
            'name',
            'description',
            'videos',
            'is_active',
        ]
        widgets = {
            'videos': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '8'}),
        }
