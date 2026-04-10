import json
import os
import tempfile

import httpx
import structlog
from facebook_business.api import FacebookAdsApi
from facebook_business.session import FacebookSession
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.adcreative import AdCreative
from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adimage import AdImage
from facebook_business.adobjects.targetingsearch import TargetingSearch
from facebook_business.exceptions import FacebookRequestError

from app.config import settings
from app.services.meta_location_resolver import MetaLocationResolver
from app.services.meta_exceptions import (
    MetaApiError,
    MetaInvalidParameterError,
    MetaMissingPermissionError,
    MetaRateLimitError,
    MetaTokenInvalidError,
    MetaValidationError,
)

logger = structlog.get_logger()

# Meta gender mapping: 1 = male, 2 = female
GENDER_MAP = {"male": 1, "female": 2}


def _build_rich_message(exc: FacebookRequestError) -> str:
    """Build a comprehensive error message from all available Meta error fields."""
    code = exc.api_error_code()
    subcode = exc.api_error_subcode() if hasattr(exc, "api_error_subcode") else None
    base_message = exc.api_error_message() if hasattr(exc, "api_error_message") else str(exc)

    body = exc.body() if hasattr(exc, "body") else {}
    error_body = body.get("error", {}) if isinstance(body, dict) else {}

    error_user_title = error_body.get("error_user_title", "")
    error_user_msg = error_body.get("error_user_msg", "")
    blame_field_specs = (
        error_body.get("error_data", {}).get("blame_field_specs", [])
        if isinstance(error_body.get("error_data"), dict) else []
    )

    parts = [f"Meta API error {code}"]
    if subcode:
        parts.append(f"(subcode: {subcode})")
    parts.append(f": {base_message}")
    if error_user_title:
        parts.append(f" | {error_user_title}")
    if error_user_msg:
        parts.append(f" | Detail: {error_user_msg}")
    if blame_field_specs:
        parts.append(f" | Blame fields: {blame_field_specs}")

    return "".join(parts)


def _handle_meta_error(exc: FacebookRequestError) -> None:
    """Map FacebookRequestError to custom exceptions with rich error details."""
    code = exc.api_error_code()
    subcode = exc.api_error_subcode() if hasattr(exc, "api_error_subcode") else None
    message = _build_rich_message(exc)

    if code == 190:
        raise MetaTokenInvalidError(message, error_code=code, error_subcode=subcode)
    elif code in (17, 613):
        raise MetaRateLimitError(message, error_code=code, error_subcode=subcode)
    elif code == 100:
        raise MetaInvalidParameterError(message, error_code=code, error_subcode=subcode)
    elif code == 275:
        raise MetaMissingPermissionError(message, error_code=code, error_subcode=subcode)
    elif code == 1487901:
        blame = None
        body = exc.body() if hasattr(exc, "body") else {}
        if isinstance(body, dict):
            blame = body.get("error", {}).get("error_data", {}).get("blame_field_specs")
        raise MetaValidationError(message, error_code=code, error_subcode=subcode, blame_field_specs=blame)
    else:
        raise MetaApiError(message, error_code=code, error_subcode=subcode)


class MetaAdsService:
    """Creates per-user FacebookAdsApi instances for multi-tenant operation.

    All methods are SYNCHRONOUS — the facebook-business SDK does not support async.
    Wrap calls in asyncio.to_thread() from async endpoints, or call directly
    from Celery tasks.
    """

    def __init__(self, access_token: str):
        session = FacebookSession(
            app_id=settings.META_APP_ID,
            app_secret=settings.META_APP_SECRET,
            access_token=access_token,
        )
        self.api = FacebookAdsApi(session)

    def _get_account(self, ad_account_id: str) -> AdAccount:
        return AdAccount(ad_account_id, api=self.api)

    def upload_image(self, ad_account_id: str, image_url: str) -> str:
        """Download image from URL and upload to Meta. Returns image_hash."""
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.get(image_url)
                response.raise_for_status()
                image_bytes = response.content

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name

            image = AdImage(parent_id=ad_account_id, api=self.api)
            image[AdImage.Field.filename] = tmp_path
            image.remote_create()

            image_hash = image[AdImage.Field.hash]
            logger.info("meta_image_uploaded", ad_account_id=ad_account_id, image_hash=image_hash)
            return image_hash
        except FacebookRequestError as exc:
            _handle_meta_error(exc)
        finally:
            # Clean up temp file
            if 'tmp_path' in locals():
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def resolve_interest_ids(self, interest_names: list[str]) -> list[dict]:
        """Resolve interest text names to Meta targeting IDs via TargetingSearch."""
        resolved = []
        for name in interest_names:
            try:
                results = TargetingSearch.search(
                    params={
                        "q": name,
                        "type": "adinterest",
                    },
                    api=self.api,
                )
                if results:
                    first = results[0]
                    resolved.append({"id": first["id"], "name": first["name"]})
                else:
                    logger.warning("meta_interest_not_found", interest=name)
            except FacebookRequestError as exc:
                error_code = exc.api_error_code()
                if error_code in (190, 17, 613):
                    _handle_meta_error(exc)
                logger.warning("meta_interest_search_failed", interest=name, error=str(exc))
        return resolved

    def create_campaign(
        self,
        ad_account_id: str,
        name: str,
        objective: str,
        special_ad_categories: list[str],
        status: str = "PAUSED",
    ) -> str:
        """Create a Meta Campaign. Returns meta_campaign_id."""
        try:
            account = self._get_account(ad_account_id)
            campaign = account.create_campaign(params={
                Campaign.Field.name: name,
                Campaign.Field.objective: objective,
                Campaign.Field.special_ad_categories: special_ad_categories,
                Campaign.Field.status: status,
                "is_adset_budget_sharing_enabled": False,
            })
            campaign_id = campaign["id"]
            logger.info("meta_campaign_created", campaign_id=campaign_id)
            return campaign_id
        except FacebookRequestError as exc:
            _handle_meta_error(exc)

    def create_adset(
        self,
        ad_account_id: str,
        campaign_id: str,
        name: str,
        daily_budget_cents: int,
        target_audience: dict,
        page_id: str,
        whatsapp_phone_number: str,
        optimization_goal: str | None = None,
        billing_event: str | None = None,
        bid_strategy: str | None = None,
    ) -> tuple[str, dict]:
        """Create a Meta Ad Set with WhatsApp targeting. Returns (meta_adset_id, resolved_geo_locations)."""
        optimization_goal = optimization_goal or settings.META_DEFAULT_OPTIMIZATION_GOAL
        billing_event = billing_event or settings.META_DEFAULT_BILLING_EVENT
        bid_strategy = bid_strategy or settings.META_DEFAULT_BID_STRATEGY

        # Build targeting spec
        # "all" in the genders list means target everyone — omit field entirely
        raw_genders = target_audience.get("genders", [])
        if "all" in raw_genders:
            genders = []
        else:
            genders = [GENDER_MAP[g] for g in raw_genders if g in GENDER_MAP]

        # Resolve locations (city-aware): supports new object format and old string format
        resolver = MetaLocationResolver(self.api)
        raw_locations = target_audience.get("locations", [{"type": "country", "country_code": "CO"}])
        geo_locations, resolved_for_storage = resolver.resolve(raw_locations)

        age_min = target_audience.get("age_min", 18)
        age_max = target_audience.get("age_max", 65)

        # Meta policy: detailed targeting (interests/behaviors) requires age_min >= 18
        # Error 100 subcode 1870249 if violated
        age_min = max(age_min, 18)
        age_max = min(age_max, 65)
        if age_max < age_min:
            age_max = age_min

        targeting = {
            "age_min": age_min,
            "age_max": age_max,
            "geo_locations": geo_locations,
            "targeting_automation": {
                "advantage_audience": 0,  # manual targeting — AdGen AI controls audience optimization
            },
        }
        if genders:
            targeting["genders"] = genders

        # Resolve interest IDs
        interest_names = target_audience.get("interests", [])
        if interest_names:
            resolved_interests = self.resolve_interest_ids(interest_names)
            if resolved_interests:
                targeting["flexible_spec"] = [{"interests": resolved_interests}]

        # Safety: widen narrow audiences to avoid Meta error 100/2446395.
        # Single city + gender + narrow age range + interests can be too small.
        is_city_targeting = "cities" in targeting.get("geo_locations", {})
        has_interests = "flexible_spec" in targeting
        age_range = targeting.get("age_max", 65) - targeting.get("age_min", 18)
        has_narrow_age = age_range <= 15

        if is_city_targeting and has_interests and has_narrow_age:
            logger.info(
                "meta_audience_widening",
                reason="city + interests + narrow age range",
                original_age_min=targeting["age_min"],
                original_age_max=targeting["age_max"],
            )
            targeting["age_min"] = max(18, targeting["age_min"] - 5)
            targeting["age_max"] = min(65, targeting["age_max"] + 5)

        logger.info(
            "meta_adset_targeting_spec",
            targeting=json.dumps(targeting, default=str),
            daily_budget_cents=daily_budget_cents,
        )

        try:
            account = self._get_account(ad_account_id)
            adset = account.create_ad_set(params={
                AdSet.Field.name: name,
                AdSet.Field.campaign_id: campaign_id,
                AdSet.Field.daily_budget: str(daily_budget_cents),
                AdSet.Field.optimization_goal: optimization_goal,
                AdSet.Field.billing_event: billing_event,
                AdSet.Field.bid_strategy: bid_strategy,
                AdSet.Field.targeting: targeting,
                AdSet.Field.destination_type: "WHATSAPP",
                AdSet.Field.promoted_object: {
                    "page_id": page_id,
                    "whatsapp_phone_number": whatsapp_phone_number,
                },
                AdSet.Field.status: "PAUSED",
            })
            adset_id = adset["id"]
            logger.info("meta_adset_created", adset_id=adset_id)
            return adset_id, resolved_for_storage
        except FacebookRequestError as exc:
            _handle_meta_error(exc)

    def create_adcreative(
        self,
        ad_account_id: str,
        name: str,
        page_id: str,
        image_hash: str,
        copy_text: str,
        whatsapp_phone_number: str,
    ) -> str:
        """Create a Meta Ad Creative for WhatsApp Click-to-Chat. Returns meta_adcreative_id."""
        try:
            account = self._get_account(ad_account_id)
            creative = account.create_ad_creative(params={
                AdCreative.Field.name: name,
                AdCreative.Field.object_story_spec: {
                    "page_id": page_id,
                    "link_data": {
                        "image_hash": image_hash,
                        "message": copy_text,
                        "link": "https://api.whatsapp.com/send",
                        "call_to_action": {
                            "type": "WHATSAPP_MESSAGE",
                            "value": {
                                "app_destination": "WHATSAPP",
                            },
                        },
                    },
                },
            })
            creative_id = creative["id"]
            logger.info("meta_adcreative_created", creative_id=creative_id)
            return creative_id
        except FacebookRequestError as exc:
            _handle_meta_error(exc)

    def create_ad(
        self,
        ad_account_id: str,
        name: str,
        adset_id: str,
        creative_id: str,
        status: str = "PAUSED",
    ) -> str:
        """Create a Meta Ad linking creative to ad set. Returns meta_ad_id."""
        try:
            account = self._get_account(ad_account_id)
            ad = account.create_ad(params={
                Ad.Field.name: name,
                Ad.Field.adset_id: adset_id,
                Ad.Field.creative: {"creative_id": creative_id},
                Ad.Field.status: status,
            })
            ad_id = ad["id"]
            logger.info("meta_ad_created", ad_id=ad_id)
            return ad_id
        except FacebookRequestError as exc:
            _handle_meta_error(exc)

    def _activate_object(self, object_id: str, object_class):
        """Set a Meta object's status to ACTIVE."""
        try:
            obj = object_class(object_id, api=self.api)
            obj.api_update(params={"status": "ACTIVE"})
        except FacebookRequestError as exc:
            _handle_meta_error(exc)

    def _archive_object(self, object_id: str, object_class):
        """Set a Meta object's status to ARCHIVED (best-effort cleanup)."""
        try:
            obj = object_class(object_id, api=self.api)
            obj.api_update(params={"status": "ARCHIVED"})
        except Exception:
            logger.warning("meta_cleanup_failed", object_id=object_id)

    def create_whatsapp_campaign(
        self,
        ad_account_id: str,
        page_id: str,
        name: str,
        copy_text: str,
        image_url: str,
        target_audience: dict,
        whatsapp_phone_number: str,
        daily_budget_cents: int,
        special_ad_categories: list[str] | None = None,
        campaign_objective: str | None = None,
    ) -> dict:
        """Create complete Meta Ads hierarchy for WhatsApp Click-to-Chat.

        Returns dict with all Meta IDs:
        {meta_campaign_id, meta_adset_id, meta_adcreative_id, meta_ad_id, meta_image_hash}
        """
        special_ad_categories = special_ad_categories if special_ad_categories is not None else []
        campaign_objective = campaign_objective or settings.META_DEFAULT_CAMPAIGN_OBJECTIVE

        created_ids = {}

        try:
            # 1. Upload image
            image_hash = self.upload_image(ad_account_id, image_url)
            created_ids["meta_image_hash"] = image_hash

            # 2. Create Campaign (PAUSED)
            meta_campaign_id = self.create_campaign(
                ad_account_id=ad_account_id,
                name=f"{name} - Campaign",
                objective=campaign_objective,
                special_ad_categories=special_ad_categories,
                status="PAUSED",
            )
            created_ids["meta_campaign_id"] = meta_campaign_id

            # 3. Create Ad Set (PAUSED)
            meta_adset_id, resolved_geo = self.create_adset(
                ad_account_id=ad_account_id,
                campaign_id=meta_campaign_id,
                name=f"{name} - Ad Set",
                daily_budget_cents=daily_budget_cents,
                target_audience=target_audience,
                page_id=page_id,
                whatsapp_phone_number=whatsapp_phone_number,
            )
            created_ids["meta_adset_id"] = meta_adset_id
            created_ids["resolved_geo_locations"] = resolved_geo

            # 4. Create Ad Creative
            meta_adcreative_id = self.create_adcreative(
                ad_account_id=ad_account_id,
                name=f"{name} - Creative",
                page_id=page_id,
                image_hash=image_hash,
                copy_text=copy_text,
                whatsapp_phone_number=whatsapp_phone_number,
            )
            created_ids["meta_adcreative_id"] = meta_adcreative_id

            # 5. Create Ad (PAUSED)
            meta_ad_id = self.create_ad(
                ad_account_id=ad_account_id,
                name=f"{name} - Ad",
                adset_id=meta_adset_id,
                creative_id=meta_adcreative_id,
                status="PAUSED",
            )
            created_ids["meta_ad_id"] = meta_ad_id

            # 6. Activate all objects
            self._activate_object(meta_campaign_id, Campaign)
            self._activate_object(meta_adset_id, AdSet)
            self._activate_object(meta_ad_id, Ad)

            logger.info("meta_whatsapp_campaign_created", **created_ids)
            return created_ids

        except (MetaTokenInvalidError, MetaRateLimitError):
            # Re-raise without cleanup for token/rate issues
            raise
        except MetaApiError:
            # Cleanup partially created objects
            self._cleanup_partial(created_ids)
            raise

    def _cleanup_partial(self, created_ids: dict) -> None:
        """Best-effort cleanup of partially created Meta objects."""
        if "meta_ad_id" in created_ids:
            self._archive_object(created_ids["meta_ad_id"], Ad)
        if "meta_adset_id" in created_ids:
            self._archive_object(created_ids["meta_adset_id"], AdSet)
        if "meta_campaign_id" in created_ids:
            self._archive_object(created_ids["meta_campaign_id"], Campaign)

    def delete_campaign(self, meta_campaign_id: str) -> None:
        """Delete an orphan campaign in Meta to keep the ad account clean."""
        try:
            campaign = Campaign(meta_campaign_id, api=self.api)
            campaign.api_update(params={Campaign.Field.status: "DELETED"})
            logger.info("meta_campaign_deleted", campaign_id=meta_campaign_id)
        except Exception:
            logger.warning("meta_campaign_delete_failed", campaign_id=meta_campaign_id)

    def get_ad_status(self, ad_id: str) -> dict:
        """Fetch current ad delivery status from Meta."""
        try:
            ad = Ad(ad_id, api=self.api)
            ad.api_get(fields=["effective_status", "status", "delivery_info"])
            return {
                "status": ad.get("status"),
                "effective_status": ad.get("effective_status"),
            }
        except FacebookRequestError as exc:
            _handle_meta_error(exc)

    def update_adset_budget(self, adset_id: str, daily_budget_cents: int) -> None:
        """Update an AdSet's daily budget in Meta."""
        try:
            adset = AdSet(adset_id, api=self.api)
            adset.api_update(params={
                AdSet.Field.daily_budget: str(daily_budget_cents),
            })
            logger.info("meta_adset_budget_updated", adset_id=adset_id, daily_budget_cents=daily_budget_cents)
        except FacebookRequestError as exc:
            _handle_meta_error(exc)

    def pause_ad(self, meta_campaign_id: str) -> None:
        """Pause a campaign in Meta (sets status to PAUSED)."""
        try:
            campaign = Campaign(meta_campaign_id, api=self.api)
            campaign.api_update(params={Campaign.Field.status: "PAUSED"})
            logger.info("meta_campaign_paused", campaign_id=meta_campaign_id)
        except FacebookRequestError as exc:
            _handle_meta_error(exc)

    def resume_ad(self, meta_campaign_id: str) -> None:
        """Resume a paused campaign in Meta (sets status to ACTIVE)."""
        try:
            campaign = Campaign(meta_campaign_id, api=self.api)
            campaign.api_update(params={Campaign.Field.status: "ACTIVE"})
            logger.info("meta_campaign_resumed", campaign_id=meta_campaign_id)
        except FacebookRequestError as exc:
            _handle_meta_error(exc)

    def archive_ad(self, meta_campaign_id: str) -> None:
        """Archive a campaign in Meta (irreversible — sets status to ARCHIVED)."""
        try:
            campaign = Campaign(meta_campaign_id, api=self.api)
            campaign.api_update(params={Campaign.Field.status: "ARCHIVED"})
            logger.info("meta_campaign_archived", campaign_id=meta_campaign_id)
        except FacebookRequestError as exc:
            _handle_meta_error(exc)

    def verify_token(self, ad_account_id: str) -> dict:
        """Verify token health with a lightweight API call."""
        try:
            account = self._get_account(ad_account_id)  # already uses api= in constructor
            account.api_get(fields=["account_id", "account_status"])
            return {"is_valid": True, "needs_reauth": False, "message": "Token is valid"}
        except FacebookRequestError as exc:
            if exc.api_error_code() == 190:
                return {"is_valid": False, "needs_reauth": True, "message": "Token is invalid or expired"}
            _handle_meta_error(exc)
