from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='dashboard', permanent=False)),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('videos/', views.GeneratedVideoListView.as_view(), name='video-list'),
    path('videos/create/', views.GeneratedVideoCreateView.as_view(), name='video-create'),
    path('videos/<int:pk>/generate/', views.generate_video, name='video_generate'),
    path('videos/<int:pk>/', views.GeneratedVideoDetailView.as_view(), name='video-detail'),
    path('videos/<int:pk>/generate/', views.video_generate, name='video-generate'),
    path('videos/<int:pk>/edit/', views.GeneratedVideoUpdateView.as_view(), name='video-edit'),
    path('videos/<int:pk>/generate/', views.generate_ai_video, name='generate-ai-video'),
    path('videos/<int:pk>/delete/', views.GeneratedVideoDeleteView.as_view(), name='video-delete'),
    path('audio/', views.AudioTrackListView.as_view(), name='audio-list'),
    path('audio/create/', views.AudioTrackCreateView.as_view(), name='audio-create'),
    path('audio/<int:pk>/', views.AudioTrackDetailView.as_view(), name='audio-detail'),
    path('audio/<int:pk>/generate/', views.GenerateAIVideoView.as_view(), name='audio-generate-video'),
    path('audio/<int:pk>/edit/', views.AudioTrackUpdateView.as_view(), name='audio-edit'),
    path('audio/<int:pk>/delete/', views.AudioTrackDeleteView.as_view(), name='audio-delete'),
    path('projects/', views.VideoProjectListView.as_view(), name='project-list'),
    path('projects/create/', views.VideoProjectCreateView.as_view(), name='project-create'),
    path('projects/<int:pk>/', views.VideoProjectDetailView.as_view(), name='project-detail'),
    path('projects/<int:pk>/edit/', views.VideoProjectUpdateView.as_view(), name='project-edit'),
    path('projects/<int:pk>/delete/', views.VideoProjectDeleteView.as_view(), name='project-delete'),
]
