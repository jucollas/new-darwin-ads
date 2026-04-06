import asyncio
import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.publishing import AdAccount, Publication
from app.schemas.publishing import AdAccountCreate, PublishRequest
from app.services.meta_ads_service import MetaAdsService
from app.services.meta_exceptions import MetaApiError, MetaTokenInvalidError
from app.services.token_encryption import decrypt_token, encrypt_token
from app.services.token_manager import TokenManager

logger = structlog.get_logger()


class PublishingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Ad Account operations
    # ------------------------------------------------------------------

    async def create_ad_account(self, user_id: str, data: AdAccountCreate) -> AdAccount:
        encrypted = encrypt_token(data.access_token)
        ad_account = AdAccount(
            user_id=user_id,
            meta_ad_account_id=data.meta_ad_account_id,
            meta_page_id=data.meta_page_id,
            meta_business_id=data.meta_business_id,
            whatsapp_phone_number=data.whatsapp_phone_number,
            access_token_encrypted=encrypted,
            token_scopes=data.token_scopes,
        )
        self.db.add(ad_account)
        await self.db.flush()
        return ad_account

    async def list_ad_accounts(self, user_id: str) -> list[AdAccount]:
        stmt = select(AdAccount).where(
            AdAccount.user_id == user_id,
            AdAccount.is_active == True,  # noqa: E712
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_ad_account(self, account_id: uuid.UUID, user_id: str) -> AdAccount | None:
        stmt = select(AdAccount).where(
            AdAccount.id == account_id,
            AdAccount.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def verify_ad_account(self, account_id: uuid.UUID, user_id: str) -> dict:
        ad_account = await self.get_ad_account(account_id, user_id)
        if not ad_account:
            return None
        manager = TokenManager(self.db)
        return await manager.verify_token(ad_account)

    async def delete_ad_account(self, account_id: uuid.UUID, user_id: str) -> bool:
        ad_account = await self.get_ad_account(account_id, user_id)
        if not ad_account:
            return False
        ad_account.is_active = False
        await self.db.flush()
        return True

    # ------------------------------------------------------------------
    # Publication operations
    # ------------------------------------------------------------------

    async def create_publication(self, user_id: str, data: PublishRequest) -> Publication:
        ad_account = await self.get_ad_account(uuid.UUID(data.ad_account_id), user_id)
        if not ad_account:
            return None
        if not ad_account.is_active:
            return None

        publication = Publication(
            campaign_id=uuid.UUID(data.campaign_id),
            proposal_id=uuid.UUID(data.proposal_id),
            ad_account_id=ad_account.id,
            special_ad_categories=data.special_ad_categories,
            destination_type=data.destination_type,
            campaign_objective=data.campaign_objective,
            budget_daily_cents=data.budget_daily_cents,
            status="queued",
        )
        self.db.add(publication)
        await self.db.flush()

        # Dispatch Celery task
        from shared.celery_app.config import celery_app
        celery_app.send_task(
            "tasks.publish_ad",
            queue="publish_tasks",
            args=[
                str(publication.id),
                str(ad_account.id),
                data.campaign_id,
                data.proposal_id,
            ],
            kwargs={
                "name": data.name or f"AdGen Campaign {data.campaign_id[:8]}",
                "budget_daily_cents": data.budget_daily_cents,
            },
        )

        logger.info("publication_queued", publication_id=str(publication.id))
        return publication

    async def list_publications(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[Publication], int]:
        # Filter by user's ad accounts
        account_ids_stmt = select(AdAccount.id).where(AdAccount.user_id == user_id)

        base = select(Publication).where(
            Publication.ad_account_id.in_(account_ids_stmt)
        )

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        items_stmt = (
            base.order_by(Publication.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(items_stmt)
        return list(result.scalars().all()), total

    async def get_publication(self, publication_id: uuid.UUID, user_id: str) -> Publication | None:
        account_ids_stmt = select(AdAccount.id).where(AdAccount.user_id == user_id)
        stmt = select(Publication).where(
            Publication.id == publication_id,
            Publication.ad_account_id.in_(account_ids_stmt),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_publication_status(self, publication_id: uuid.UUID, user_id: str) -> dict | None:
        publication = await self.get_publication(publication_id, user_id)
        if not publication:
            return None

        result = {
            "id": publication.id,
            "status": publication.status,
            "meta_effective_status": None,
            "delivery_status": None,
        }

        # Fetch live status from Meta if we have a meta_ad_id
        if publication.meta_ad_id and publication.status in ("active", "paused"):
            ad_account = await self.db.get(AdAccount, publication.ad_account_id)
            if ad_account and ad_account.is_active:
                try:
                    token = decrypt_token(ad_account.access_token_encrypted)
                    service = MetaAdsService(token)
                    meta_status = await asyncio.to_thread(
                        service.get_ad_status, publication.meta_ad_id
                    )
                    result["meta_effective_status"] = meta_status.get("effective_status")
                    result["delivery_status"] = meta_status.get("status")
                except Exception:
                    logger.warning("meta_status_fetch_failed", publication_id=str(publication_id))

        return result

    async def pause_publication(self, publication_id: uuid.UUID, user_id: str) -> Publication | None:
        publication = await self.get_publication(publication_id, user_id)
        if not publication or publication.status != "active":
            return None

        ad_account = await self.db.get(AdAccount, publication.ad_account_id)
        if not ad_account or not publication.meta_campaign_id:
            return None

        token = decrypt_token(ad_account.access_token_encrypted)
        service = MetaAdsService(token)
        try:
            await asyncio.to_thread(service.pause_ad, publication.meta_campaign_id)
        except MetaTokenInvalidError:
            manager = TokenManager(self.db)
            await manager.flag_for_reauth(ad_account)
            raise
        except MetaApiError:
            raise

        publication.status = "paused"
        await self.db.flush()
        return publication

    async def resume_publication(self, publication_id: uuid.UUID, user_id: str) -> Publication | None:
        publication = await self.get_publication(publication_id, user_id)
        if not publication or publication.status != "paused":
            return None

        ad_account = await self.db.get(AdAccount, publication.ad_account_id)
        if not ad_account or not publication.meta_campaign_id:
            return None

        token = decrypt_token(ad_account.access_token_encrypted)
        service = MetaAdsService(token)
        try:
            await asyncio.to_thread(service.resume_ad, publication.meta_campaign_id)
        except MetaTokenInvalidError:
            manager = TokenManager(self.db)
            await manager.flag_for_reauth(ad_account)
            raise
        except MetaApiError:
            raise

        publication.status = "active"
        await self.db.flush()
        return publication

    async def delete_publication(self, publication_id: uuid.UUID, user_id: str) -> bool:
        publication = await self.get_publication(publication_id, user_id)
        if not publication:
            return False

        if publication.meta_campaign_id:
            ad_account = await self.db.get(AdAccount, publication.ad_account_id)
            if ad_account:
                try:
                    token = decrypt_token(ad_account.access_token_encrypted)
                    service = MetaAdsService(token)
                    await asyncio.to_thread(service.archive_ad, publication.meta_campaign_id)
                except Exception:
                    logger.warning("meta_archive_failed", publication_id=str(publication_id))

        publication.status = "archived"
        await self.db.flush()
        return True
