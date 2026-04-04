import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth.jwt_middleware import get_current_user
from shared.database.session import get_db
from app.schemas.campaign import (
    CampaignCreate,
    CampaignDetailResponse,
    CampaignListResponse,
    CampaignResponse,
    CampaignUpdate,
    ProposalResponse,
    ProposalUpdate,
)
from app.services.campaign_service import CampaignService

router = APIRouter(tags=["campaigns"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": "campaign-service"}


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")


@router.post("/", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: CampaignCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CampaignService(db)
    campaign = await service.create(user_id=current_user["user_id"], data=data)
    return campaign


@router.get("/", response_model=CampaignListResponse)
async def list_campaigns(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CampaignService(db)
    items, total = await service.list_by_user(
        user_id=current_user["user_id"],
        status=status,
        page=page,
        page_size=page_size,
    )
    return CampaignListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{campaign_id}", response_model=CampaignDetailResponse)
async def get_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CampaignService(db)
    campaign = await service.get_by_id(_parse_uuid(campaign_id), current_user["user_id"])
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: str,
    data: CampaignUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CampaignService(db)
    campaign = await service.update(_parse_uuid(campaign_id), current_user["user_id"], data)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CampaignService(db)
    deleted = await service.delete(_parse_uuid(campaign_id), current_user["user_id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Campaign not found")


@router.post("/{campaign_id}/generate", response_model=CampaignResponse)
async def generate_proposals(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CampaignService(db)
    campaign = await service.generate_proposals(_parse_uuid(campaign_id), current_user["user_id"])
    if not campaign:
        raise HTTPException(status_code=400, detail="Cannot generate proposals for this campaign")
    return campaign


@router.get("/{campaign_id}/proposals", response_model=list[ProposalResponse])
async def get_proposals(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CampaignService(db)
    return await service.get_proposals(_parse_uuid(campaign_id), current_user["user_id"])


@router.put("/{campaign_id}/proposals/{proposal_id}", response_model=ProposalResponse)
async def update_proposal(
    campaign_id: str,
    proposal_id: str,
    data: ProposalUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CampaignService(db)
    proposal = await service.update_proposal(
        _parse_uuid(campaign_id), _parse_uuid(proposal_id), current_user["user_id"], data,
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal


@router.post("/{campaign_id}/select/{proposal_id}", response_model=CampaignResponse)
async def select_proposal(
    campaign_id: str,
    proposal_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CampaignService(db)
    campaign = await service.select_proposal(
        _parse_uuid(campaign_id), _parse_uuid(proposal_id), current_user["user_id"],
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign or proposal not found")

    # Get selected proposal to extract image_prompt
    proposals = await service.get_proposals(_parse_uuid(campaign_id), current_user["user_id"])
    selected = next((p for p in proposals if str(p.id) == proposal_id), None)

    if selected and selected.image_url:
        # Already has an image — skip generation
        await service.update_status(campaign_id, "image_ready")
    elif selected:
        # Dispatch image generation task
        from shared.celery_app.config import celery_app
        celery_app.send_task(
            "tasks.image_generate",
            queue="image_tasks",
            args=[
                str(campaign.id),
                proposal_id,
                selected.image_prompt,
                "1:1",
            ],
        )

    return campaign


@router.post("/{campaign_id}/publish", response_model=CampaignResponse)
async def publish_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CampaignService(db)
    campaign = await service.publish(_parse_uuid(campaign_id), current_user["user_id"])
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CampaignService(db)
    campaign = await service.pause(_parse_uuid(campaign_id), current_user["user_id"])
    if not campaign:
        raise HTTPException(status_code=400, detail="Campaign cannot be paused")
    return campaign


@router.post("/{campaign_id}/resume", response_model=CampaignResponse)
async def resume_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CampaignService(db)
    campaign = await service.resume(_parse_uuid(campaign_id), current_user["user_id"])
    if not campaign:
        raise HTTPException(status_code=400, detail="Campaign cannot be resumed")
    return campaign


# ---------------------------------------------------------------------------
# Internal endpoints — called by other services, NO JWT required
# ---------------------------------------------------------------------------


@router.post("/internal/{campaign_id}/store-proposals", include_in_schema=False)
async def store_proposals_internal(
    campaign_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint called by ai-generation-service Celery task."""
    data = await request.json()
    service = CampaignService(db)
    campaign = await service.get_by_id_internal(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    await service.delete_proposals(campaign_id)
    for proposal_data in data["proposals"]:
        await service.create_proposal(campaign_id, proposal_data)
    await service.update_status(campaign_id, "proposals_ready")

    return {"status": "ok", "proposals_stored": len(data["proposals"])}


@router.put("/internal/{campaign_id}/proposals/{proposal_id}/image", include_in_schema=False)
async def update_proposal_image_internal(
    campaign_id: str,
    proposal_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint called by image-generation-service to set image_url on a proposal."""
    data = await request.json()
    service = CampaignService(db)
    updated = await service.update_proposal_image(
        campaign_id, proposal_id, data["image_url"], data.get("storage_path"),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return {"status": "ok"}


@router.put("/internal/{campaign_id}/status", include_in_schema=False)
async def update_status_internal(
    campaign_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint to update campaign status from other services."""
    data = await request.json()
    service = CampaignService(db)
    await service.update_status(campaign_id, data["status"])
    return {"status": "ok"}
