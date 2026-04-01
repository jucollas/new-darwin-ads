import uuid

from fastapi import APIRouter, Depends, HTTPException, status
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
