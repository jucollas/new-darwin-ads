import asyncio
import os

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shared.celery_app.config import celery_app

logger = structlog.get_logger()

NOTIFICATION_TITLES = {
    "optimization_complete": "Optimization cycle completed",
    "campaign_published": "Campaign published",
    "token_expiring": "Meta token expiring soon",
    "metrics_collected": "Metrics collected",
    "image_generated": "Image generated",
}


def _get_async_session() -> async_sessionmaker[AsyncSession]:
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://adgen:changeme_in_production@postgres:5432/adgen_ai",
    )
    engine = create_async_engine(database_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _store_notification(user_id: str, notification_type: str, data: dict | None = None):
    from app.models.notification import Notification

    title = NOTIFICATION_TITLES.get(notification_type, notification_type)
    session_factory = _get_async_session()
    async with session_factory() as session:
        try:
            notification = Notification(
                user_id=user_id,
                type=notification_type,
                title=title,
                data=data,
            )
            session.add(notification)
            await session.commit()
            logger.info(
                "notification_stored",
                user_id=user_id,
                type=notification_type,
            )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@celery_app.task(
    bind=True,
    name="tasks.notification_send",
    queue="notification_tasks",
    max_retries=2,
    default_retry_delay=30,
)
def notification_send(self, user_id: str, notification_type: str, data: dict | None = None):
    """Store a notification in the database."""
    logger.info(
        "notification_task_start",
        user_id=user_id,
        type=notification_type,
    )
    try:
        asyncio.run(_store_notification(user_id, notification_type, data))
    except Exception as exc:
        logger.error(
            "notification_task_failed",
            user_id=user_id,
            type=notification_type,
            error=str(exc),
        )
        raise self.retry(exc=exc)
