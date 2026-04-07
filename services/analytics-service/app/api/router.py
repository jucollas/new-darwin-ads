import uuid
from datetime import date

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth.jwt_middleware import get_current_user
from shared.celery_app.config import celery_app
from shared.database.session import get_db
from app.schemas.metric import (
    CollectRequest,
    MetricListResponse,
    MetricSummary,
    TopPerformerResponse,
)
from app.services.analytics_service import AnalyticsService

logger = structlog.get_logger()
router = APIRouter(tags=["metrics"])


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")


# ---------------------------------------------------------------------------
# Static routes MUST come before /{campaign_id} to avoid UUID parsing issues
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=MetricSummary)
async def get_summary(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated metrics summary across all user campaigns."""
    service = AnalyticsService(db)
    summary = await service.get_summary(
        current_user["user_id"], from_date=from_date, to_date=to_date
    )
    return MetricSummary(**summary)


@router.get("/top-performers", response_model=list[TopPerformerResponse])
async def get_top_performers(
    limit: int = Query(default=5, ge=1, le=20),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Top performing campaigns by ROAS/CTR in the last 7 days."""
    service = AnalyticsService(db)
    results = await service.get_top_performers(current_user["user_id"], limit=limit)
    return [TopPerformerResponse(**r) for r in results]


@router.get("/underperformers", response_model=list[TopPerformerResponse])
async def get_underperformers(
    limit: int = Query(default=5, ge=1, le=20),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Worst performing campaigns by CTR/CPC in the last 7 days."""
    service = AnalyticsService(db)
    results = await service.get_underperformers(current_user["user_id"], limit=limit)
    return [TopPerformerResponse(**r) for r in results]


@router.post("/collect", status_code=status.HTTP_202_ACCEPTED)
async def trigger_collection(
    data: CollectRequest = CollectRequest(),
    current_user: dict = Depends(get_current_user),
):
    """Manually trigger metric collection. Dispatches a Celery task."""
    celery_app.send_task(
        "tasks.analytics_collect",
        queue="analytics_tasks",
        args=[data.lookback_days, current_user["user_id"]],
    )
    logger.info(
        "metrics_collection_triggered",
        user_id=current_user["user_id"],
        lookback_days=data.lookback_days,
    )
    return {"message": "Metric collection task dispatched", "lookback_days": data.lookback_days}


# ---------------------------------------------------------------------------
# Dynamic route — must be last
# ---------------------------------------------------------------------------


@router.get("/{campaign_id}", response_model=MetricListResponse)
async def get_campaign_metrics(
    campaign_id: str,
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Metrics for a specific campaign with optional date filtering."""
    cid = _parse_uuid(campaign_id)
    service = AnalyticsService(db)
    metrics = await service.get_campaign_metrics(
        cid, current_user["user_id"], from_date=from_date, to_date=to_date
    )
    return MetricListResponse(items=metrics, total=len(metrics))
