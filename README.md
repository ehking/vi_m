# music_video_panel

A local-first Django application for managing audio tracks and AI-generated music videos with a dashboard, CRUD UI, Django admin, and REST API.

## Installation

1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Database setup

```bash
python manage.py migrate
```

If you see errors like `no such column: videos_generatedvideo.generation_progress` when loading the
video list, it means your local SQLite database is missing the latest schema changes. Re-run the
`migrate` command above to create the new columns and retry the page.

## Create superuser

```bash
python manage.py createsuperuser
```

## Run dev server

```bash
python manage.py runserver
```

## Access URLs

- Admin: `/admin/`
- Dashboard: `/dashboard/`
- Video list: `/videos/`
- Audio list: `/audio/`
- Projects: `/projects/`
- API: `/api/`

MEDIA files are stored under `media/` and served locally in DEBUG mode.
