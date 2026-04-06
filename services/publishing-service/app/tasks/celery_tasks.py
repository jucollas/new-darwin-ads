from datetime import datetime, timedelta

import httpx
import structlog

from shared.celery_app.config import celery_app
from app.models.publishing import AdAccount
from facebook_business.exceptions import FacebookBadObjectError
from app.services.meta_ads_service import MetaAdsService
from app.services.meta_exceptions import MetaApiError, MetaRateLimitError, MetaTokenInvalidError
from app.services.sync_db import get_sync_session
from app.services.token_encryption import decrypt_token, encrypt_token

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    name="tasks.publish_ad",
    queue="publish_tasks",
    max_retries=3,
    autoretry_for=(),
    default_retry_delay=60,
    time_limit=300,
    soft_time_limit=240,
)
def publish_ad_task(
    self,
    publication_id: str,
    ad_account_id: str,
    campaign_id: str,
    proposal_id: str,
    name: str = "AdGen Campaign",
    budget_daily_cents: int = 1000,
):
    """
    Publish an ad to Meta Ads.
    1. Fetch proposal details from campaign-service
    2. Fetch ad account, decrypt token
    3. Create full Meta Ads hierarchy via SDK
    4. Update publication with Meta IDs
    5. Update campaign status
    6. Dispatch notification
    """
    meta_ids = {}
    service = None

    try:
        logger.info("publish_task_start", publication_id=publication_id, campaign_id=campaign_id)

        # Update publication status to "publishing"
        _update_publication_status(publication_id, "publishing")

        # Step 1: Fetch proposal details from campaign-service
        proposal = _fetch_proposal(campaign_id, proposal_id)

        # Step 2: Fetch ad account from DB, decrypt token
        import uuid as _uuid

        session = get_sync_session()
        try:
            ad_account = session.query(AdAccount).filter(
                AdAccount.id == _uuid.UUID(ad_account_id)
            ).first()
            if not ad_account:
                raise ValueError(f"Ad account {ad_account_id} not found")

            token = decrypt_token(ad_account.access_token_encrypted)
            meta_ad_account_id = ad_account.meta_ad_account_id
            page_id = ad_account.meta_page_id
            whatsapp_number = ad_account.whatsapp_phone_number or proposal.get("whatsapp_number") or None
        finally:
            session.close()

        # Fail fast if no WhatsApp number is available — do NOT proceed to Meta API
        if not whatsapp_number:
            error_msg = (
                "Cannot publish WhatsApp ad: no WhatsApp phone number configured. "
                f"Set it via PUT /api/v1/publish/ad-accounts/{ad_account_id}/whatsapp"
            )
            _update_publication_status(publication_id, "failed", error_message=error_msg)
            _update_campaign_status(campaign_id, "failed")
            logger.error("publish_task_no_whatsapp", publication_id=publication_id)
            return  # Do NOT retry — this is a data issue, not transient

        # Step 3: Create Meta Ads hierarchy with incremental saves
        service = MetaAdsService(token)

        # 3a. Upload image
        image_hash = service.upload_image(meta_ad_account_id, proposal["image_url"])
        meta_ids["meta_image_hash"] = image_hash
        _update_publication_status(publication_id, "publishing", meta_ids=dict(meta_ids))

        # 3b. Create Campaign (PAUSED)
        from app.config import settings as pub_settings
        campaign_objective = pub_settings.META_DEFAULT_CAMPAIGN_OBJECTIVE
        meta_campaign_id = service.create_campaign(
            ad_account_id=meta_ad_account_id,
            name=f"{name} - Campaign",
            objective=campaign_objective,
            special_ad_categories=[],
            status="PAUSED",
        )
        meta_ids["meta_campaign_id"] = meta_campaign_id
        _update_publication_status(publication_id, "publishing", meta_ids=dict(meta_ids))

        # 3c. Create Ad Set (PAUSED)
        meta_adset_id = service.create_adset(
            ad_account_id=meta_ad_account_id,
            campaign_id=meta_campaign_id,
            name=f"{name} - Ad Set",
            daily_budget_cents=budget_daily_cents,
            target_audience=proposal["target_audience"],
            page_id=page_id,
            whatsapp_phone_number=whatsapp_number,
        )
        meta_ids["meta_adset_id"] = meta_adset_id
        _update_publication_status(publication_id, "publishing", meta_ids=dict(meta_ids))

        # 3d. Create Ad Creative
        meta_adcreative_id = service.create_adcreative(
            ad_account_id=meta_ad_account_id,
            name=f"{name} - Creative",
            page_id=page_id,
            image_hash=image_hash,
            copy_text=proposal["copy_text"],
            whatsapp_phone_number=whatsapp_number,
        )
        meta_ids["meta_adcreative_id"] = meta_adcreative_id
        _update_publication_status(publication_id, "publishing", meta_ids=dict(meta_ids))

        # 3e. Create Ad (PAUSED)
        meta_ad_id = service.create_ad(
            ad_account_id=meta_ad_account_id,
            name=f"{name} - Ad",
            adset_id=meta_adset_id,
            creative_id=meta_adcreative_id,
            status="PAUSED",
        )
        meta_ids["meta_ad_id"] = meta_ad_id
        _update_publication_status(publication_id, "publishing", meta_ids=dict(meta_ids))

        # 3f. Activate all objects
        from facebook_business.adobjects.campaign import Campaign
        from facebook_business.adobjects.adset import AdSet
        from facebook_business.adobjects.ad import Ad
        service._activate_object(meta_campaign_id, Campaign)
        service._activate_object(meta_adset_id, AdSet)
        service._activate_object(meta_ad_id, Ad)

        # Step 4: Update publication with final status
        _update_publication_status(publication_id, "active", meta_ids=meta_ids)

        # Step 5: Update campaign status to "published"
        _update_campaign_status(campaign_id, "published")

        # Step 6: Dispatch notification
        try:
            celery_app.send_task(
                "tasks.notification_send",
                queue="notification_tasks",
                args=[campaign_id, "campaign_published"],
            )
        except Exception:
            logger.warning("publish_task_notification_failed", campaign_id=campaign_id)

        logger.info("publish_task_complete", publication_id=publication_id, **meta_ids)

    except MetaTokenInvalidError as exc:
        logger.error("publish_task_token_invalid", publication_id=publication_id, error=str(exc))
        _cleanup_orphan_campaign(service, meta_ids)
        _update_publication_status(
            publication_id, "failed",
            error_message=exc.message, error_code=exc.error_code,
        )
        _update_campaign_status(campaign_id, "failed")
        _flag_ad_account_inactive(ad_account_id)
        # Do NOT retry — token is invalid

    except MetaRateLimitError as exc:
        logger.warning("publish_task_rate_limited", publication_id=publication_id, error=str(exc))
        countdown = 2 ** self.request.retries * 60
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=countdown)
        _cleanup_orphan_campaign(service, meta_ids)
        _update_publication_status(
            publication_id, "failed",
            error_message=exc.message, error_code=exc.error_code,
        )
        _update_campaign_status(campaign_id, "failed")

    except MetaApiError as exc:
        logger.error("publish_task_meta_error", publication_id=publication_id, error=str(exc))
        _cleanup_orphan_campaign(service, meta_ids)
        _update_publication_status(
            publication_id, "failed",
            error_message=exc.message, error_code=exc.error_code,
        )
        _update_campaign_status(campaign_id, "failed")

    except FacebookBadObjectError as exc:
        # SDK configuration/code error — NOT transient, do NOT retry
        logger.error("publish_task_sdk_error", publication_id=publication_id, error=str(exc))
        _cleanup_orphan_campaign(service, meta_ids)
        _update_publication_status(
            publication_id, "failed",
            error_message=f"SDK configuration error: {str(exc)}",
        )
        _update_campaign_status(campaign_id, "failed")

    except Exception as exc:
        logger.exception("publish_task_unexpected_error", publication_id=publication_id)
        _cleanup_orphan_campaign(service, meta_ids)
        _update_publication_status(
            publication_id, "failed",
            error_message=f"Unexpected error: {str(exc)[:500]}",
        )
        _update_campaign_status(campaign_id, "failed")
        # Do NOT retry unknown errors — only transient errors (rate limit) are retried above


@celery_app.task(
    bind=True,
    name="tasks.token_refresh_all",
    queue="token_refresh_tasks",
    soft_time_limit=300,
    time_limit=360,
)
def refresh_tokens_task(self):
    """
    Daily task to check and refresh Meta tokens:
    1. Query all active ad accounts
    2. Verify token health
    3. Refresh tokens approaching 45-day expiry
    4. Flag invalid tokens for re-auth
    """
    logger.info("token_refresh_start")
    session = get_sync_session()

    try:
        accounts = session.query(AdAccount).filter(AdAccount.is_active == True).all()  # noqa: E712
        refreshed = 0
        flagged = 0

        for account in accounts:
            try:
                token = decrypt_token(account.access_token_encrypted)
                service = MetaAdsService(token)
                result = service.verify_token(account.meta_ad_account_id)

                if result.get("needs_reauth"):
                    account.is_active = False
                    flagged += 1
                    # Dispatch notification
                    try:
                        celery_app.send_task(
                            "tasks.notification_send",
                            queue="notification_tasks",
                            args=[account.user_id, "token_expiring"],
                        )
                    except Exception:
                        pass
                elif account.token_expires_at:
                    threshold = datetime.utcnow() + timedelta(days=45)
                    if account.token_expires_at <= threshold:
                        # Attempt refresh
                        from app.services.meta_oauth_service import MetaOAuthService
                        oauth = MetaOAuthService()
                        try:
                            import asyncio
                            loop = asyncio.new_event_loop()
                            refresh_result = loop.run_until_complete(
                                oauth.exchange_for_long_lived_token(token)
                            )
                            loop.close()

                            account.access_token_encrypted = encrypt_token(refresh_result["access_token"])
                            expires_in = refresh_result.get("expires_in")
                            if expires_in:
                                account.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                            refreshed += 1
                        except Exception:
                            logger.warning("token_refresh_exchange_failed", account_id=str(account.id))

                account.token_last_verified_at = datetime.utcnow()

            except Exception:
                logger.exception("token_refresh_account_error", account_id=str(account.id))

        session.commit()
        logger.info("token_refresh_complete", total=len(accounts), refreshed=refreshed, flagged=flagged)
        return {"total": len(accounts), "refreshed": refreshed, "flagged": flagged}

    except Exception:
        session.rollback()
        logger.exception("token_refresh_task_error")
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Helper functions (sync httpx calls to internal endpoints)
# ---------------------------------------------------------------------------


def _cleanup_orphan_campaign(service: MetaAdsService | None, meta_ids: dict) -> None:
    """Delete orphan Meta campaign created before a later step failed."""
    campaign_id = meta_ids.get("meta_campaign_id")
    if not service or not campaign_id:
        return
    try:
        service.delete_campaign(campaign_id)
        logger.info("cleanup_orphan_campaign", campaign_id=campaign_id)
    except Exception as cleanup_err:
        logger.warning("cleanup_orphan_failed", campaign_id=campaign_id, error=str(cleanup_err))


def _fetch_proposal(campaign_id: str, proposal_id: str) -> dict:
    """Fetch proposal details from campaign-service."""
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"http://campaign-service:8001/api/v1/campaigns/internal/{campaign_id}/proposal/{proposal_id}"
        )
        response.raise_for_status()
        return response.json()


def _update_publication_status(
    publication_id: str,
    status: str,
    meta_ids: dict | None = None,
    error_message: str | None = None,
    error_code: int | None = None,
) -> None:
    """Update publication status via internal endpoint."""
    payload = {"status": status}
    if meta_ids:
        payload["meta_ids"] = meta_ids
    if error_message is not None:
        payload["error_message"] = error_message
    if error_code is not None:
        payload["error_code"] = error_code

    try:
        with httpx.Client(timeout=10.0) as client:
            client.put(
                f"http://publishing-service:8004/api/v1/publish/internal/{publication_id}/status",
                json=payload,
            )
    except Exception:
        logger.exception("publish_status_update_failed", publication_id=publication_id)


def _update_campaign_status(campaign_id: str, status: str) -> None:
    """Update campaign status via campaign-service internal endpoint."""
    try:
        with httpx.Client(timeout=10.0) as client:
            client.put(
                f"http://campaign-service:8001/api/v1/campaigns/internal/{campaign_id}/status",
                json={"status": status},
            )
    except Exception:
        logger.exception("campaign_status_update_failed", campaign_id=campaign_id)


def _flag_ad_account_inactive(ad_account_id: str) -> None:
    """Flag ad account as inactive via sync DB."""
    import uuid as _uuid
    session = get_sync_session()
    try:
        account = session.query(AdAccount).filter(
            AdAccount.id == _uuid.UUID(ad_account_id)
        ).first()
        if account:
            account.is_active = False
            session.commit()
    except Exception:
        session.rollback()
        logger.exception("flag_account_inactive_failed", ad_account_id=ad_account_id)
    finally:
        session.close()
