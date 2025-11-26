from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AudioTrack',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('artist', models.CharField(blank=True, max_length=255)),
                ('audio_file', models.FileField(upload_to='audio/')),
                ('lyrics', models.TextField(blank=True)),
                ('language', models.CharField(blank=True, max_length=10)),
                ('bpm', models.IntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='GeneratedVideo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('video_file', models.FileField(upload_to='videos/')),
                ('thumbnail', models.ImageField(blank=True, null=True, upload_to='thumbnails/')),
                ('file_size_bytes', models.BigIntegerField(blank=True, null=True)),
                ('duration_seconds', models.IntegerField(blank=True, null=True)),
                ('resolution', models.CharField(blank=True, max_length=50)),
                ('aspect_ratio', models.CharField(blank=True, max_length=20)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('pending', 'Pending'), ('processing', 'Processing'), ('ready', 'Ready'), ('failed', 'Failed'), ('archived', 'Archived')], default='draft', max_length=20)),
                ('error_message', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('tags', models.TextField(blank=True)),
                ('mood', models.CharField(blank=True, choices=[('sad', 'Sad'), ('happy', 'Happy'), ('epic', 'Epic'), ('romantic', 'Romantic'), ('dark', 'Dark'), ('chill', 'Chill')], max_length=20)),
                ('prompt_used', models.TextField(blank=True)),
                ('model_name', models.CharField(blank=True, max_length=100)),
                ('generation_time_ms', models.IntegerField(blank=True, null=True)),
                ('seed', models.IntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('audio_track', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='videos', to='videos.audiotrack')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='VideoProject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('videos', models.ManyToManyField(blank=True, related_name='projects', to='videos.generatedvideo')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=100)),
                ('object_type', models.CharField(max_length=100)),
                ('object_id', models.IntegerField(blank=True, null=True)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
