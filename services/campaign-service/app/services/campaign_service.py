import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.campaign import Campaign, Proposal
from app.schemas.campaign import CampaignCreate, CampaignUpdate, ProposalUpdate


VALID_STATUSES = {
    "draft", "generating", "proposals_ready", "image_generating",
    "image_ready", "publishing", "published", "paused", "failed", "archived",
}


class CampaignService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: str, data: CampaignCreate) -> Campaign:
        campaign = Campaign(user_id=user_id, user_prompt=data.user_prompt)
        self.db.add(campaign)
        await self.db.flush()
        return campaign

    async def get_by_id(self, campaign_id: uuid.UUID, user_id: str) -> Campaign | None:
        stmt = (
            select(Campaign)
            .options(selectinload(Campaign.proposals))
            .where(Campaign.id == campaign_id, Campaign.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_internal(self, campaign_id: str) -> Campaign | None:
        """Get campaign without user_id check (for internal service calls)."""
        stmt = select(Campaign).where(Campaign.id == uuid.UUID(campaign_id))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: str,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Campaign], int]:
        base = select(Campaign).where(
            Campaign.user_id == user_id,
            Campaign.status != "archived",
        )
        if status:
            if status == "archived":
                base = select(Campaign).where(
                    Campaign.user_id == user_id,
                    Campaign.status == "archived",
                )
            else:
                base = base.where(Campaign.status == status)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        items_stmt = base.order_by(Campaign.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(items_stmt)
        return list(result.scalars().all()), total

    async def update(self, campaign_id: uuid.UUID, user_id: str, data: CampaignUpdate) -> Campaign | None:
        campaign = await self.get_by_id(campaign_id, user_id)
        if not campaign:
            return None
        if data.user_prompt is not None:
            campaign.user_prompt = data.user_prompt
        if data.status is not None and data.status in VALID_STATUSES:
            campaign.status = data.status
        if data.selected_proposal_id is not None:
            campaign.selected_proposal_id = uuid.UUID(data.selected_proposal_id)
        await self.db.flush()
        return campaign

    async def delete(self, campaign_id: uuid.UUID, user_id: str) -> bool:
        campaign = await self.get_by_id(campaign_id, user_id)
        if not campaign:
            return False
        campaign.status = "archived"
        await self.db.flush()
        return True

    async def generate_proposals(self, campaign_id: uuid.UUID, user_id: str) -> Campaign | None:
        """Dispatch AI proposal generation (sync or async based on config)."""
        from app.config import settings

        campaign = await self.get_by_id(campaign_id, user_id)
        if not campaign:
            return None
        if campaign.status not in ("draft", "proposals_ready", "failed"):
            return None

        # Remove existing proposals
        for p in list(campaign.proposals):
            await self.db.delete(p)
        await self.db.flush()

        campaign.status = "generating"
        campaign.selected_proposal_id = None
        await self.db.flush()

        if settings.USE_SYNC_AI:
            # Synchronous mode — call ai-generation-service directly
            import httpx

            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    response = await client.post(
                        f"{settings.AI_SERVICE_URL}/api/v1/ai/generate/proposals",
                        json={
                            "user_prompt": campaign.user_prompt,
                            "business_context": {},
                        },
                    )
                    response.raise_for_status()
                    proposals_data = response.json()["proposals"]

                # Store proposals directly
                await self.delete_proposals(str(campaign.id))
                for p in proposals_data:
                    await self.create_proposal(str(campaign.id), p)
                await self.update_status(str(campaign.id), "proposals_ready")

            except Exception as e:
                await self.update_status(str(campaign.id), "failed")
                await self.db.flush()
                await self.db.refresh(campaign)
                return campaign
        else:
            # Async mode — dispatch Celery task
            from shared.celery_app.config import celery_app
            celery_app.send_task(
                "tasks.ai_generate_proposals",
                queue="ai_tasks",
                args=[str(campaign.id), campaign.user_prompt, {}],
            )

        await self.db.flush()
        await self.db.refresh(campaign)
        return campaign

    async def delete_proposals(self, campaign_id: str) -> None:
        """Delete all proposals for a campaign (for regeneration)."""
        stmt = delete(Proposal).where(Proposal.campaign_id == uuid.UUID(campaign_id))
        await self.db.execute(stmt)

    async def create_proposal(self, campaign_id: str, data: dict) -> Proposal:
        """Create a proposal from AI-generated data."""
        proposal = Proposal(
            campaign_id=uuid.UUID(campaign_id),
            copy_text=data["copy_text"],
            script=data["script"],
            image_prompt=data["image_prompt"],
            target_audience=data["target_audience"],
            cta_type=data.get("cta_type", "whatsapp_chat"),
            whatsapp_number=data.get("whatsapp_number"),
        )
        self.db.add(proposal)
        await self.db.flush()
        return proposal

    async def update_proposal_image(
        self,
        campaign_id: str,
        proposal_id: str,
        image_url: str,
        storage_path: str | None = None,
    ) -> bool:
        """Update a proposal's image_url (called by image-generation-service)."""
        stmt = (
            update(Proposal)
            .where(
                Proposal.campaign_id == uuid.UUID(campaign_id),
                Proposal.id == uuid.UUID(proposal_id),
            )
            .values(image_url=image_url)
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def update_status(self, campaign_id: str, status: str) -> None:
        """Update campaign status."""
        stmt = (
            update(Campaign)
            .where(Campaign.id == uuid.UUID(campaign_id))
            .values(status=status, updated_at=datetime.utcnow())
        )
        await self.db.execute(stmt)

    async def get_proposals(self, campaign_id: uuid.UUID, user_id: str) -> list[Proposal]:
        campaign = await self.get_by_id(campaign_id, user_id)
        if not campaign:
            return []
        return list(campaign.proposals)

    async def update_proposal(
        self,
        campaign_id: uuid.UUID,
        proposal_id: uuid.UUID,
        user_id: str,
        data: ProposalUpdate,
    ) -> Proposal | None:
        campaign = await self.get_by_id(campaign_id, user_id)
        if not campaign:
            return None

        proposal = None
        for p in campaign.proposals:
            if p.id == proposal_id:
                proposal = p
                break
        if not proposal:
            return None

        changed = False
        if data.copy_text is not None:
            proposal.copy_text = data.copy_text
            changed = True
        if data.script is not None:
            proposal.script = data.script
            changed = True
        if data.image_prompt is not None:
            proposal.image_prompt = data.image_prompt
            changed = True
        if data.target_audience is not None:
            proposal.target_audience = data.target_audience
            changed = True
        if data.cta_type is not None:
            proposal.cta_type = data.cta_type
            changed = True
        if data.whatsapp_number is not None:
            proposal.whatsapp_number = data.whatsapp_number
            changed = True

        if changed:
            proposal.is_edited = True

        await self.db.flush()
        return proposal

    async def select_proposal(
        self,
        campaign_id: uuid.UUID,
        proposal_id: uuid.UUID,
        user_id: str,
    ) -> Campaign | None:
        campaign = await self.get_by_id(campaign_id, user_id)
        if not campaign:
            return None

        found = False
        for p in campaign.proposals:
            if p.id == proposal_id:
                p.is_selected = True
                found = True
            else:
                p.is_selected = False

        if not found:
            return None

        campaign.selected_proposal_id = proposal_id
        campaign.status = "image_generating"
        await self.db.flush()
        return campaign

    async def publish(self, campaign_id: uuid.UUID, user_id: str) -> Campaign | None:
        campaign = await self.get_by_id(campaign_id, user_id)
        if not campaign:
            return None
        campaign.status = "published"
        await self.db.flush()
        return campaign

    async def pause(self, campaign_id: uuid.UUID, user_id: str) -> Campaign | None:
        campaign = await self.get_by_id(campaign_id, user_id)
        if not campaign or campaign.status != "published":
            return None
        campaign.status = "paused"
        await self.db.flush()
        return campaign

    async def resume(self, campaign_id: uuid.UUID, user_id: str) -> Campaign | None:
        campaign = await self.get_by_id(campaign_id, user_id)
        if not campaign or campaign.status != "paused":
            return None
        campaign.status = "published"
        await self.db.flush()
        return campaign
