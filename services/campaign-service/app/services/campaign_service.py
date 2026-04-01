import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.campaign import Campaign, Proposal
from app.schemas.campaign import CampaignCreate, CampaignUpdate, ProposalUpdate


VALID_STATUSES = {
    "draft", "generating", "proposals_ready", "image_generating",
    "image_ready", "publishing", "published", "paused", "failed", "archived",
}


def _generate_mock_proposals(campaign: Campaign) -> list[dict]:
    base_prompt = campaign.user_prompt
    return [
        {
            "copy_text": f"Propuesta 1: \u00a1Descubre lo mejor! {base_prompt[:80]}... Escr\u00edbenos por WhatsApp y recibe asesor\u00eda personalizada.",
            "script": f"Escena 1: Mostrar producto/servicio relacionado con: {base_prompt[:60]}.\nEscena 2: Cliente satisfecho.\nEscena 3: Call to action - WhatsApp.",
            "image_prompt": f"Professional advertising photo, modern and clean design, related to: {base_prompt[:60]}, vibrant colors, white background, commercial photography style",
            "target_audience": {"age_min": 25, "age_max": 45, "genders": ["male", "female"], "interests": ["shopping", "lifestyle"], "locations": ["CO"]},
            "cta_type": "whatsapp_chat",
            "whatsapp_number": None,
        },
        {
            "copy_text": f"Propuesta 2: \u00bfBuscas {base_prompt[:50]}? Tenemos la soluci\u00f3n perfecta para ti. \u00a1Chatea con nosotros ahora!",
            "script": f"Escena 1: Problema del cliente.\nEscena 2: Soluci\u00f3n con {base_prompt[:40]}.\nEscena 3: Testimonial.\nEscena 4: WhatsApp CTA.",
            "image_prompt": f"Eye-catching social media ad, bold typography, product showcase related to: {base_prompt[:60]}, professional lighting, Instagram-ready",
            "target_audience": {"age_min": 18, "age_max": 35, "genders": ["female"], "interests": ["fashion", "beauty", "wellness"], "locations": ["CO"]},
            "cta_type": "whatsapp_chat",
            "whatsapp_number": None,
        },
        {
            "copy_text": f"Propuesta 3: Oferta exclusiva - {base_prompt[:50]}. Solo por tiempo limitado. \u00a1No te lo pierdas! Escr\u00edbenos ya.",
            "script": f"Escena 1: Urgencia - oferta limitada.\nEscena 2: Producto destacado: {base_prompt[:40]}.\nEscena 3: Precio/descuento.\nEscena 4: Bot\u00f3n WhatsApp.",
            "image_prompt": f"Sale promotion banner, urgency design, countdown timer aesthetic, related to: {base_prompt[:60]}, red and yellow accents, commercial",
            "target_audience": {"age_min": 20, "age_max": 50, "genders": ["male", "female"], "interests": ["deals", "promotions", "online shopping"], "locations": ["CO", "MX"]},
            "cta_type": "whatsapp_chat",
            "whatsapp_number": None,
        },
    ]


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
        campaign = await self.get_by_id(campaign_id, user_id)
        if not campaign:
            return None
        if campaign.status not in ("draft", "proposals_ready"):
            return None

        # Remove existing proposals
        for p in list(campaign.proposals):
            await self.db.delete(p)
        await self.db.flush()

        campaign.status = "generating"
        await self.db.flush()

        # Create mock proposals
        mock_data = _generate_mock_proposals(campaign)
        for data in mock_data:
            proposal = Proposal(campaign_id=campaign.id, **data)
            self.db.add(proposal)

        campaign.status = "proposals_ready"
        campaign.selected_proposal_id = None
        await self.db.flush()

        # Reload proposals
        await self.db.refresh(campaign)
        return campaign

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
