from django import forms
from .models import AudioTrack, GeneratedVideo, VideoProject


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        status_field = self.fields.get('status')
        if status_field:
            status_field.required = False
            status_field.initial = (
                status_field.initial
                or self._meta.model._meta.get_field('status').default
            )

    def clean_status(self):
        status = self.cleaned_data.get('status')
        if not status:
            return self._meta.model._meta.get_field('status').default
        return status


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
