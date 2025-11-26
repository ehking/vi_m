from django.http import HttpResponseServerError
from django.template.loader import render_to_string
from django.db.utils import OperationalError


class SchemaHealthcheckMiddleware:
    """Catch missing migration errors and surface actionable guidance.

    When the SQLite database is missing newer columns (e.g. the
    ``generation_progress`` column on ``GeneratedVideo``), Django raises an
    ``OperationalError`` that results in a 500 response. This middleware
    intercepts that specific failure and returns a helpful HTML message that
    instructs the operator to run migrations instead of exposing a raw
    traceback.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except OperationalError as exc:
            if "videos_generatedvideo.generation_progress" not in str(exc):
                raise

            content = render_to_string(
                "videos/schema_error.html",
                {
                    "error": exc,
                    "migration_command": "python manage.py migrate",
                },
            )
            return HttpResponseServerError(content)
