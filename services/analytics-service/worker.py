"""Celery worker entry point — imports shared app + registers tasks."""
from shared.celery_app.config import celery_app  # noqa: F401
import app.tasks.celery_tasks  # noqa: F401
