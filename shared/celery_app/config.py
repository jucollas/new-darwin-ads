from celery import Celery
from celery.schedules import crontab
import os

celery_app = Celery(
    "adgen_ai",
    broker=os.getenv("REDIS_URL", "redis://redis:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://redis:6379/0"),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_routes={
        "tasks.ai_*": {"queue": "ai_tasks"},
        "tasks.image_*": {"queue": "image_tasks"},
        "tasks.publish_*": {"queue": "publish_tasks"},
        "tasks.token_*": {"queue": "token_refresh_tasks"},
        "tasks.analytics_*": {"queue": "analytics_tasks"},
        "tasks.genetic_*": {"queue": "genetic_tasks"},
        "tasks.notification_*": {"queue": "notification_tasks"},
    },
    beat_schedule={
        "refresh-meta-tokens-daily": {
            "task": "tasks.token_refresh_all",
            "schedule": crontab(hour=3, minute=0),
            "options": {"queue": "token_refresh_tasks"},
        },
    },
)
