from django import forms
from django.apps import apps

from .models import AudioTrack, GeneratedVideo, VideoProject
from .styles import get_default_prompt_for_style


def _get_ai_provider_model():
    return apps.get_model("videos", "AIProviderConfig")


def _get_ai_video_job_model():
    return apps.get_model("videos", "AIVideoJob")


class StyledModelForm(forms.ModelForm):
    """Base form that adds Bootstrap-friendly classes to widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            existing_classes = widget.attrs.get("class", "").split()

            if isinstance(widget, forms.CheckboxInput):
                self._ensure_class(widget, existing_classes, "form-check-input")
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                self._ensure_class(widget, existing_classes, "form-select")
            else:
                self._ensure_class(widget, existing_classes, "form-control")

    @staticmethod
    def _ensure_class(widget, existing_classes, class_name):
        if class_name not in existing_classes:
            widget.attrs["class"] = " ".join(existing_classes + [class_name]).strip()


class AudioTrackForm(StyledModelForm):
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


class GeneratedVideoForm(StyledModelForm):
    class Meta:
        model = GeneratedVideo
        fields = [
            'audio_track',
            'title',
            'description',
            'video_file',
            'background_video',
            'thumbnail',
            'style',
            'style_prompt',
            'extra_prompt',
            'mood',
            'tags',
            'status',
            'prompt_used',
            'model_name',
            'seed',
            'generation_time_ms',
            'generation_progress',
            'generation_log',
            'error_code',
            'resolution',
            'aspect_ratio',
            'is_active',
        ]
        widgets = {
            'generation_progress': forms.NumberInput(attrs={'min': 0, 'max': 100}),
            'generation_log': forms.Textarea(attrs={'rows': 4}),
            'style_prompt': forms.Textarea(attrs={'rows': 4}),
            'extra_prompt': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        status_field = self.fields.get('status')
        if status_field:
            status_field.required = False
            status_field.initial = (
                status_field.initial
                or self._meta.model._meta.get_field('status').default
            )

        style_field = self.fields.get('style')
        if style_field:
            style_field.required = False
            style_field.initial = style_field.initial or self._meta.model._meta.get_field('style').default

        # Auto-populate style prompt when creating a new instance or when a style is preset
        if 'style_prompt' in self.fields:
            current_style = self.initial.get('style') or getattr(self.instance, 'style', None)
            if not self.initial.get('style_prompt') and current_style:
                self.initial['style_prompt'] = get_default_prompt_for_style(current_style)

    def clean_status(self):
        status = self.cleaned_data.get('status')
        if not status:
            return self._meta.model._meta.get_field('status').default
        return status

    def clean_style(self):
        style = self.cleaned_data.get('style')
        if not style:
            return self._meta.model._meta.get_field('style').default
        return style


class GeneratedVideoStatusForm(StyledModelForm):
    class Meta:
        model = GeneratedVideo
        fields = [
            'status',
            'tags',
            'mood',
            'prompt_used',
            'model_name',
            'generation_progress',
            'error_message',
            'video_file',
        ]
        widgets = {
            'generation_progress': forms.NumberInput(attrs={'min': 0, 'max': 100}),
            'prompt_used': forms.Textarea(attrs={'rows': 3}),
            'error_message': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_generation_progress(self):
        progress = self.cleaned_data.get('generation_progress')
        if progress is None or progress == '':
            return None
        try:
            progress_int = int(progress)
        except (TypeError, ValueError):
            raise forms.ValidationError('Generation progress must be an integer between 0 and 100.')
        if progress_int < 0 or progress_int > 100:
            raise forms.ValidationError('Generation progress must be between 0 and 100.')
        return progress_int


class VideoProjectForm(StyledModelForm):
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


class AIProviderConfigForm(StyledModelForm):
    class Meta:
        model = _get_ai_provider_model()
        fields = [
            'name',
            'base_url',
            'endpoint_path',
            'api_key',
            'extra_headers',
            'extra_payload',
            'is_active',
        ]
        widgets = {
            'extra_headers': forms.Textarea(attrs={'rows': 3}),
            'extra_payload': forms.Textarea(attrs={'rows': 4}),
        }


class AIVideoJobCreateForm(StyledModelForm):
    class Meta:
        model = _get_ai_video_job_model()
        fields = [
            'provider',
            'audio_track',
            'background_video',
            'prompt',
        ]
        widgets = {
            'prompt': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        provider_model = _get_ai_provider_model()
        if 'provider' in self.fields:
            self.fields['provider'].queryset = provider_model.objects.filter(is_active=True)
