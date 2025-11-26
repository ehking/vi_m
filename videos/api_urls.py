from rest_framework.routers import DefaultRouter
from django.urls import path, include

from .api_views import AudioTrackViewSet, GeneratedVideoViewSet, VideoProjectViewSet

router = DefaultRouter()
router.register(r'videos', GeneratedVideoViewSet, basename='api-videos')
router.register(r'audio', AudioTrackViewSet, basename='api-audio')
router.register(r'projects', VideoProjectViewSet, basename='api-projects')

urlpatterns = [
    path('', include(router.urls)),
]
