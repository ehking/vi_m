from rest_framework import serializers
from .models import AudioTrack, GeneratedVideo, VideoProject


class AudioTrackSerializer(serializers.ModelSerializer):
    class Meta:
        model = AudioTrack
        fields = '__all__'


class GeneratedVideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedVideo
        fields = '__all__'


class VideoProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoProject
        fields = '__all__'
