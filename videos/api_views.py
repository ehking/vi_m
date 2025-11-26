from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AudioTrack, GeneratedVideo, VideoProject
from .api_serializers import AudioTrackSerializer, GeneratedVideoSerializer, VideoProjectSerializer


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

    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        video = self.get_object()
        status_value = request.data.get('status')
        error_message = request.data.get('error_message', '')
        if status_value:
            video.status = status_value
        video.error_message = error_message
        video.save(update_fields=['status', 'error_message'])
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
