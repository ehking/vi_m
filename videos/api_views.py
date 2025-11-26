from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AudioTrack, GeneratedVideo, VideoProject
from .api_serializers import AudioTrackSerializer, GeneratedVideoSerializer, VideoProjectSerializer


DEFAULT_PROGRESS_BY_STATUS = {
    "draft": 0,
    "pending": 25,
    "processing": 75,
    "ready": 100,
    "archived": 100,
}


class GeneratedVideoViewSet(viewsets.ModelViewSet):
    queryset = GeneratedVideo.objects.all().select_related('audio_track')
    serializer_class = GeneratedVideoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = self.request.query_params.get('status')
        mood = self.request.query_params.get('mood')
        audio_track = self.request.query_params.get('audio_track')
        if status_param:
            qs = qs.filter(status=status_param)
        if mood:
            qs = qs.filter(mood=mood)
        if audio_track:
            qs = qs.filter(audio_track_id=audio_track)
        return qs

    @action(detail=False, methods=['get'], url_path='pending')
    def list_pending(self, request):
        queryset = self.get_queryset().filter(status='pending')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        video = self.get_object()
        status_value = request.data.get('status')
        error_message = request.data.get('error_message', '')
        error_code = request.data.get('error_code', '')
        generation_log = request.data.get('generation_log')
        progress_value = request.data.get('generation_progress')
        if progress_value == '':
            progress_value = None
        video_file_path = request.data.get('video_file')
        fields_to_update = []

        if status_value:
            video.status = status_value
            fields_to_update.append('status')

            if progress_value is None:
                default_progress = DEFAULT_PROGRESS_BY_STATUS.get(status_value)
                if default_progress is not None:
                    video.generation_progress = default_progress
                    fields_to_update.append('generation_progress')

        video.error_message = error_message
        fields_to_update.append('error_message')

        if error_code is not None:
            video.error_code = error_code
            fields_to_update.append('error_code')

        if progress_value is not None:
            try:
                video.generation_progress = max(0, min(100, int(progress_value)))
                fields_to_update.append('generation_progress')
            except (TypeError, ValueError):
                return Response(
                    {"detail": "generation_progress must be an integer between 0 and 100."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if generation_log is not None:
            log_entry = str(generation_log)
            if video.generation_log:
                video.generation_log = f"{video.generation_log}\n{log_entry}"
            else:
                video.generation_log = log_entry
            fields_to_update.append('generation_log')

        if video_file_path is not None:
            video.video_file.name = str(video_file_path)
            fields_to_update.append('video_file')

        video.save(update_fields=fields_to_update)
        serializer = self.get_serializer(video)
        return Response(serializer.data)


class AudioTrackViewSet(viewsets.ModelViewSet):
    queryset = AudioTrack.objects.all()
    serializer_class = AudioTrackSerializer
    permission_classes = [IsAuthenticated]


class VideoProjectViewSet(viewsets.ModelViewSet):
    queryset = VideoProject.objects.all()
    serializer_class = VideoProjectSerializer
    permission_classes = [IsAuthenticated]
