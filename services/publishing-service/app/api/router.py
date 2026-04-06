import uuid
from datetime import datetime, timedelta

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth.jwt_middleware import get_current_user
from shared.database.session import get_db
from app.config import settings
from app.models.publishing import AdAccount
from app.schemas.publishing import (
    AdAccountCreate,
    AdAccountListResponse,
    AdAccountResponse,
    AdAccountVerifyResponse,
    PublicationListResponse,
    PublicationResponse,
    PublicationStatusResponse,
    PublishRequest,
    SetWhatsAppNumberRequest,
)
from app.services.meta_exceptions import MetaApiError, MetaTokenInvalidError
from app.services.meta_oauth_service import MetaOAuthService, OAUTH_SCOPES
from app.services.publishing_service import PublishingService
from app.services.token_encryption import encrypt_token

logger = structlog.get_logger()
router = APIRouter(tags=["publishing"])

_redis = None


async def _get_redis():
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")


# ---------------------------------------------------------------------------
# OAuth endpoints
# ---------------------------------------------------------------------------


@router.get("/auth/meta/login")
async def meta_oauth_login(current_user: dict = Depends(get_current_user)):
    """Redirect user to Meta OAuth authorization dialog."""
    state_nonce = str(uuid.uuid4())
    user_id = current_user["user_id"]

    # Store state -> user_id in Redis (TTL 10 min)
    r = await _get_redis()
    await r.setex(f"oauth_state:{state_nonce}", 600, user_id)

    oauth_service = MetaOAuthService()
    login_url = oauth_service.generate_login_url(state=state_nonce)
    return {"login_url": login_url}


@router.get("/auth/meta/callback")
async def meta_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle Meta OAuth callback — exchange code for long-lived token."""
    # Validate state from Redis (atomic get-and-delete)
    r = await _get_redis()
    user_id = await r.getdel(f"oauth_state:{state}")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    oauth_service = MetaOAuthService()

    # Exchange code for short-lived token
    try:
        token_data = await oauth_service.exchange_code_for_token(code)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code")

    short_lived_token = token_data.get("access_token")
    if not short_lived_token:
        raise HTTPException(status_code=400, detail="Meta did not return an access token")

    # Exchange for long-lived token
    try:
        long_lived_data = await oauth_service.exchange_for_long_lived_token(short_lived_token)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to obtain long-lived token")

    long_lived_token = long_lived_data.get("access_token")
    if not long_lived_token:
        raise HTTPException(status_code=400, detail="Meta did not return a long-lived token")
    expires_in = long_lived_data.get("expires_in")
    token_expires_at = None
    if expires_in:
        token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    # Fetch user's ad accounts and pages
    ad_accounts = await oauth_service.fetch_user_ad_accounts(long_lived_token)
    pages = await oauth_service.fetch_user_pages(long_lived_token)

    page_id = pages[0]["id"] if pages else settings.PAGE_ID
    encrypted_token = encrypt_token(long_lived_token)

    # Store each ad account
    created = []
    for acct in ad_accounts:
        ad_account = AdAccount(
            user_id=user_id,
            meta_ad_account_id=f"act_{acct['account_id']}",
            meta_page_id=page_id,
            meta_business_id=acct.get("business", {}).get("id") if acct.get("business") else None,
            access_token_encrypted=encrypted_token,
            token_expires_at=token_expires_at,
            token_scopes=OAUTH_SCOPES.split(","),
            is_active=True,
        )
        # Set default WhatsApp number from config if available
        if settings.WHATSAPP_DEFAULT_PHONE_NUMBER:
            ad_account.whatsapp_phone_number = settings.WHATSAPP_DEFAULT_PHONE_NUMBER

        db.add(ad_account)
        created.append(ad_account)

    await db.flush()

    logger.info("oauth_callback_success", user_id=user_id, accounts_linked=len(created))

    # Redirect to frontend success page
    return RedirectResponse(url=f"/?oauth=success&accounts={len(created)}")


# ---------------------------------------------------------------------------
# Ad Account endpoints (all JWT-protected)
# ---------------------------------------------------------------------------


@router.post("/ad-accounts", response_model=AdAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_ad_account(
    data: AdAccountCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PublishingService(db)
    account = await service.create_ad_account(current_user["user_id"], data)
    return account


@router.get("/ad-accounts", response_model=AdAccountListResponse)
async def list_ad_accounts(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PublishingService(db)
    accounts = await service.list_ad_accounts(current_user["user_id"])
    return AdAccountListResponse(
        items=accounts, total=len(accounts), page=1, page_size=len(accounts)
    )


@router.get("/ad-accounts/{account_id}/verify", response_model=AdAccountVerifyResponse)
async def verify_ad_account(
    account_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PublishingService(db)
    result = await service.verify_ad_account(_parse_uuid(account_id), current_user["user_id"])
    if result is None:
        raise HTTPException(status_code=404, detail="Ad account not found")
    return AdAccountVerifyResponse(**result)


@router.delete("/ad-accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ad_account(
    account_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PublishingService(db)
    deleted = await service.delete_ad_account(_parse_uuid(account_id), current_user["user_id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Ad account not found")


@router.put("/ad-accounts/{account_id}/whatsapp", response_model=AdAccountResponse)
async def set_whatsapp_number(
    account_id: str,
    data: SetWhatsAppNumberRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set the WhatsApp phone number for an ad account."""
    from sqlalchemy import select

    account_uuid = _parse_uuid(account_id)
    result = await db.execute(
        select(AdAccount).where(
            AdAccount.id == account_uuid,
            AdAccount.user_id == current_user["user_id"],
            AdAccount.is_active == True,  # noqa: E712
        )
    )
    ad_account = result.scalar_one_or_none()
    if not ad_account:
        raise HTTPException(status_code=404, detail="Ad account not found")

    ad_account.whatsapp_phone_number = data.whatsapp_number
    await db.flush()
    return ad_account


# ---------------------------------------------------------------------------
# Publication endpoints (all JWT-protected)
# ---------------------------------------------------------------------------


@router.post("/", response_model=PublicationResponse, status_code=status.HTTP_201_CREATED)
async def create_publication(
    data: PublishRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PublishingService(db)
    publication = await service.create_publication(current_user["user_id"], data)
    if publication is None:
        raise HTTPException(status_code=400, detail="Invalid ad account or ad account is inactive")
    return publication


@router.get("/publications", response_model=PublicationListResponse)
async def list_publications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PublishingService(db)
    items, total = await service.list_publications(
        current_user["user_id"], page=page, page_size=page_size
    )
    return PublicationListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/publications/{publication_id}/status", response_model=PublicationStatusResponse)
async def get_publication_status(
    publication_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PublishingService(db)
    result = await service.get_publication_status(
        _parse_uuid(publication_id), current_user["user_id"]
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    return PublicationStatusResponse(**result)


@router.post("/publications/{publication_id}/pause", response_model=PublicationResponse)
async def pause_publication(
    publication_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PublishingService(db)
    try:
        publication = await service.pause_publication(
            _parse_uuid(publication_id), current_user["user_id"]
        )
    except MetaTokenInvalidError:
        raise HTTPException(status_code=401, detail="Meta token is invalid, please re-authenticate")
    except MetaApiError as exc:
        raise HTTPException(status_code=502, detail=f"Meta API error: {exc.message}")
    if publication is None:
        raise HTTPException(status_code=400, detail="Publication not found or cannot be paused")
    return publication


@router.post("/publications/{publication_id}/resume", response_model=PublicationResponse)
async def resume_publication(
    publication_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PublishingService(db)
    try:
        publication = await service.resume_publication(
            _parse_uuid(publication_id), current_user["user_id"]
        )
    except MetaTokenInvalidError:
        raise HTTPException(status_code=401, detail="Meta token is invalid, please re-authenticate")
    except MetaApiError as exc:
        raise HTTPException(status_code=502, detail=f"Meta API error: {exc.message}")
    if publication is None:
        raise HTTPException(status_code=400, detail="Publication not found or cannot be resumed")
    return publication


@router.delete("/publications/{publication_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_publication(
    publication_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PublishingService(db)
    deleted = await service.delete_publication(
        _parse_uuid(publication_id), current_user["user_id"]
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Publication not found")


# ---------------------------------------------------------------------------
# Internal endpoints — called by Celery tasks, NO JWT required
# ---------------------------------------------------------------------------


@router.put("/internal/{publication_id}/status", include_in_schema=False)
async def update_publication_status_internal(
    publication_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint called by Celery tasks to update publication status."""
    from sqlalchemy import update
    from app.models.publishing import Publication

    data = await request.json()
    new_status = data.get("status")
    meta_ids = data.get("meta_ids", {})

    values = {"status": new_status}
    if meta_ids:
        for key in ("meta_campaign_id", "meta_adset_id", "meta_adcreative_id",
                     "meta_ad_id", "meta_image_hash"):
            if key in meta_ids:
                values[key] = meta_ids[key]
    if new_status == "active":
        values["published_at"] = datetime.utcnow()
    if "error_message" in data:
        values["error_message"] = data["error_message"]
    if "error_code" in data:
        values["error_code"] = data["error_code"]

    stmt = (
        update(Publication)
        .where(Publication.id == uuid.UUID(publication_id))
        .values(**values)
    )
    await db.execute(stmt)
    return {"status": "ok"}
