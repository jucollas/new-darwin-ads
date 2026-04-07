import asyncio
import os

import structlog
from celery.schedules import crontab
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shared.celery_app.config import celery_app

logger = structlog.get_logger()


def _get_async_session() -> async_sessionmaker[AsyncSession]:
    """Create an async session factory for use in Celery tasks."""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://adgen:changeme_in_production@postgres:5432/adgen_ai",
    )
    engine = create_async_engine(database_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _run_optimization_async(user_id: str) -> dict:
    """Async wrapper for the optimization cycle."""
    from app.models.genetic import GeneticConfig  # noqa: F811
    from app.services.optimizer import OptimizationOrchestrator

    session_factory = _get_async_session()
    async with session_factory() as session:
        try:
            orchestrator = OptimizationOrchestrator(session)
            run = await orchestrator.run_optimization(user_id)
            await session.commit()
            return {
                "run_id": str(run.id),
                "generation": run.generation_number,
                "evaluated": run.campaigns_evaluated,
                "killed": len(run.campaigns_killed),
                "duplicated": len(run.campaigns_duplicated),
            }
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@celery_app.task(
    bind=True,
    name="tasks.genetic_optimize",
    queue="genetic_tasks",
    max_retries=1,
    default_retry_delay=300,
    soft_time_limit=600,
    time_limit=720,
)
def run_optimization_task(self, user_id: str):
    """Celery task that runs the optimization cycle."""
    logger.info("optimization_task_start", user_id=user_id)
    try:
        result = asyncio.run(_run_optimization_async(user_id))
        logger.info("optimization_task_complete", user_id=user_id, **result)
        return result
    except Exception as exc:
        logger.error(
            "optimization_task_failed",
            user_id=user_id,
            error=str(exc),
        )
        raise self.retry(exc=exc)


async def _get_all_config_user_ids() -> list[str]:
    """Query all GeneticConfig rows and return their user_ids."""
    from app.models.genetic import GeneticConfig

    session_factory = _get_async_session()
    async with session_factory() as session:
        result = await session.execute(select(GeneticConfig.user_id))
        return [row[0] for row in result.all()]


@celery_app.task(name="tasks.genetic_dispatch", queue="genetic_tasks")
def dispatch_optimizations():
    """Dispatch one optimization task per user with a GeneticConfig."""
    try:
        user_ids = asyncio.run(_get_all_config_user_ids())
    except Exception as exc:
        logger.error("dispatch_query_failed", error=str(exc))
        return {"dispatched": 0, "error": str(exc)}

    if not user_ids:
        logger.info("dispatch_no_configs")
        return {"dispatched": 0}

    for uid in user_ids:
        run_optimization_task.delay(uid)
        logger.info("optimization_dispatched", user_id=uid)

    return {"dispatched": len(user_ids)}


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Celery Beat: run optimization every 24 hours at 3:00 AM UTC."""
    sender.add_periodic_task(
        crontab(hour=3, minute=0),
        dispatch_optimizations.s(),
        name="daily-genetic-optimization",
    )
