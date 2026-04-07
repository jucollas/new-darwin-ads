import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth.jwt_middleware import get_current_user
from shared.database.session import get_db
from app.models.genetic import GeneticConfig, OptimizationRun
from app.schemas.genetic import (
    GeneticConfigResponse,
    GeneticConfigUpdate,
    OptimizationRunDetail,
    OptimizationRunListResponse,
    OptimizationRunResponse,
)
from app.services.optimizer import OptimizationOrchestrator

logger = structlog.get_logger()
router = APIRouter(tags=["optimize"])


# --- Static routes first ---


@router.get("/config", response_model=GeneticConfigResponse)
async def get_config(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current config. Auto-creates with defaults if none exists."""
    user_id = current_user["user_id"]
    result = await db.execute(
        select(GeneticConfig).where(GeneticConfig.user_id == user_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        config = GeneticConfig(user_id=user_id)
        db.add(config)
        await db.flush()
        await db.refresh(config)

    return config


@router.put("/config", response_model=GeneticConfigResponse)
async def update_config(
    data: GeneticConfigUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update genetic algorithm config. Creates with defaults if none exists."""
    user_id = current_user["user_id"]
    result = await db.execute(
        select(GeneticConfig).where(GeneticConfig.user_id == user_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        config = GeneticConfig(user_id=user_id)
        db.add(config)
        await db.flush()

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(config, field, value)

    await db.flush()
    await db.refresh(config)
    return config


# --- CRUD routes ---


@router.post(
    "/",
    response_model=OptimizationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def run_optimization(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manual trigger for optimization cycle."""
    user_id = current_user["user_id"]
    token = ""  # Token would come from request header in real use
    orchestrator = OptimizationOrchestrator(db)
    run = await orchestrator.run_optimization(user_id, token=token)
    return run


@router.get("/", response_model=OptimizationRunListResponse)
async def list_optimization_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List optimization run history for the current user, newest first."""
    user_id = current_user["user_id"]

    # Count
    count_result = await db.execute(
        select(func.count(OptimizationRun.id)).where(
            OptimizationRun.user_id == user_id
        )
    )
    total = count_result.scalar_one()

    # Query with pagination
    offset = (page - 1) * page_size
    result = await db.execute(
        select(OptimizationRun)
        .where(OptimizationRun.user_id == user_id)
        .order_by(OptimizationRun.ran_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    runs = result.scalars().all()

    return OptimizationRunListResponse(
        items=[OptimizationRunResponse.model_validate(r) for r in runs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{run_id}", response_model=OptimizationRunDetail)
async def get_optimization_run(
    run_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detail of one optimization run."""
    user_id = current_user["user_id"]
    result = await db.execute(
        select(OptimizationRun).where(
            OptimizationRun.id == run_id,
            OptimizationRun.user_id == user_id,
        )
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Optimization run not found",
        )

    return run
