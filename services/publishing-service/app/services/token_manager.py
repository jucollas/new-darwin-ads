import asyncio
from datetime import datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.publishing import AdAccount
from app.services.meta_ads_service import MetaAdsService
from app.services.meta_oauth_service import MetaOAuthService
from app.services.token_encryption import decrypt_token, encrypt_token

logger = structlog.get_logger()


class TokenManager:
    """Manages Meta access token lifecycle: verification, refresh, and re-auth flagging."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def verify_token(self, ad_account: AdAccount) -> dict:
        """Verify token health via a lightweight Meta API call."""
        token = decrypt_token(ad_account.access_token_encrypted)
        service = MetaAdsService(token)
        result = await asyncio.to_thread(
            service.verify_token, ad_account.meta_ad_account_id
        )

        ad_account.token_last_verified_at = datetime.utcnow()

        if result.get("needs_reauth"):
            await self.flag_for_reauth(ad_account)

        await self.db.flush()
        return result

    async def check_token_expiry(self, ad_account: AdAccount) -> bool:
        """Check if token is approaching the 45-day mark and needs refresh."""
        if ad_account.token_expires_at is None:
            return False
        threshold = datetime.utcnow() + timedelta(days=45)
        return ad_account.token_expires_at <= threshold

    async def refresh_token(self, ad_account: AdAccount) -> bool:
        """Refresh a token approaching expiry via fb_exchange_token."""
        try:
            token = decrypt_token(ad_account.access_token_encrypted)
            oauth_service = MetaOAuthService()
            result = await oauth_service.exchange_for_long_lived_token(token)

            new_token = result["access_token"]
            expires_in = result.get("expires_in")

            ad_account.access_token_encrypted = encrypt_token(new_token)
            if expires_in:
                ad_account.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            ad_account.token_last_verified_at = datetime.utcnow()
            await self.db.flush()

            logger.info("token_refreshed", ad_account_id=str(ad_account.id))
            return True
        except Exception:
            logger.exception("token_refresh_failed", ad_account_id=str(ad_account.id))
            return False

    async def flag_for_reauth(self, ad_account: AdAccount) -> None:
        """Flag an ad account for re-authentication (token invalid)."""
        ad_account.is_active = False
        await self.db.flush()

        logger.warning("ad_account_flagged_reauth", ad_account_id=str(ad_account.id))

        # Dispatch token_expiring notification (best-effort)
        try:
            from shared.celery_app.config import celery_app
            celery_app.send_task(
                "tasks.notification_send",
                queue="notification_tasks",
                args=[str(ad_account.user_id), "token_expiring"],
            )
        except Exception:
            logger.warning("token_notification_dispatch_failed", ad_account_id=str(ad_account.id))
