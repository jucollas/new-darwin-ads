"""
MVP auto-seed: ensure a Meta ad account exists after database reset.

Called during FastAPI lifespan startup. If no ad accounts exist and
META_ACCESS_TOKEN is set, creates one using env var credentials and
the dev-auth service for user_id resolution.

In production/multi-user mode this function does nothing because
ad accounts are created via the OAuth flow.
"""

import logging

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.publishing import AdAccount
from app.services.token_encryption import encrypt_token

logger = logging.getLogger(__name__)

TOKEN_SCOPES = [
    "ads_management",
    "ads_read",
    "pages_manage_ads",
    "pages_read_engagement",
    "pages_show_list",
    "business_management",
]

DEV_AUTH_URL = "http://dev-auth-service:8000/api/auth/login"


async def _resolve_user_id() -> str:
    """Login to dev-auth and return the user_id (JWT sub claim)."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            DEV_AUTH_URL,
            json={"email": "dev@adgen.ai", "password": "dev123456"},
        )
        resp.raise_for_status()
    return resp.json()["user"]["id"]


async def seed_meta_account_if_empty(db: AsyncSession) -> None:
    """
    MVP auto-seed: If no ad accounts exist and META_ACCESS_TOKEN is set,
    create one using env var credentials. This ensures the dev environment
    always has a working Meta ad account after docker compose down -v.

    In production/multi-user mode, this function does nothing because
    ad accounts are created via OAuth flow.
    """
    if settings.ENVIRONMENT not in ("development", "local", "dev"):
        return

    if not settings.META_ACCESS_TOKEN:
        logger.info("MVP auto-seed: Skipped — META_ACCESS_TOKEN not configured")
        return

    required = {
        "AD_ACCOUNT_ID": settings.AD_ACCOUNT_ID,
        "PAGE_ID": settings.PAGE_ID,
        "META_TOKEN_ENCRYPTION_KEY": settings.META_TOKEN_ENCRYPTION_KEY,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        logger.warning(
            "MVP auto-seed: Skipped — missing required settings: %s",
            ", ".join(missing),
        )
        return

    try:
        count_result = await db.execute(
            select(func.count()).select_from(AdAccount)
        )
        count = count_result.scalar_one()

        if count > 0:
            logger.info(
                "MVP auto-seed: Skipped — %d ad account(s) already exist", count
            )
            return

        user_id = await _resolve_user_id()

        encrypted_token = encrypt_token(settings.META_ACCESS_TOKEN)

        ad_account = AdAccount(
            user_id=user_id,
            meta_ad_account_id=settings.AD_ACCOUNT_ID,
            meta_page_id=settings.PAGE_ID,
            meta_business_id=settings.BUSINESS_MANAGER_ID or None,
            whatsapp_phone_number=settings.WHATSAPP_DEFAULT_PHONE_NUMBER,
            access_token_encrypted=encrypted_token,
            token_scopes=TOKEN_SCOPES,
            is_active=True,
        )
        db.add(ad_account)
        await db.commit()

        logger.info(
            "MVP auto-seed: Created Meta ad account %s for user %s",
            settings.AD_ACCOUNT_ID,
            user_id,
        )
    except Exception:
        await db.rollback()
        logger.warning(
            "MVP auto-seed: Failed to seed ad account — service will start anyway",
            exc_info=True,
        )
