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

Run migrations again whenever you pull new changes so newly added columns (for example, generation
progress and logging fields) are created in your local database and the dashboard can load without
errors.

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
