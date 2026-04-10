#!/usr/bin/env python3
"""
One-time recovery script: Fetches all active campaigns from Meta Ads
and re-creates local database records across all schemas.

Usage:
    docker compose exec publishing-service python /app/scripts/recover_from_meta.py

Environment: Uses META_ACCESS_TOKEN, META_AD_ACCOUNT_ID, META_PAGE_ID from env vars.
Database: Connects directly to PostgreSQL and writes to campaign_schema,
          publishing_schema, analytics_schema.
"""

import asyncio
import json
import logging
import uuid
from datetime import date, datetime, timedelta

from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.ad import Ad as MetaAd
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adcreative import AdCreative as MetaAdCreative
from facebook_business.adobjects.adset import AdSet as MetaAdSet
from facebook_business.adobjects.campaign import Campaign as MetaCampaign
from facebook_business.session import FacebookSession
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.services.token_encryption import encrypt_token
from shared.utils.meta_credentials import get_meta_credentials

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

DATABASE_URL = settings.DATABASE_URL
OWNER_USER_ID = "owner"

# Meta gender mapping (inverse of GENDER_MAP in meta_ads_service.py)
GENDER_REVERSE_MAP = {1: "male", 2: "female"}

# WhatsApp conversion action types (same as meta_insights_service.py)
MESSAGING_ACTION_TYPES = {
    "onsite_conversion.messaging_conversation_started_7d",
    "onsite_conversion.messaging_conversation_started",
    "messages",
}

# Namespace for deterministic UUID generation — ensures idempotency across re-runs
_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def deterministic_uuid(prefix: str, meta_id: str) -> uuid.UUID:
    """Generate a deterministic UUID from a Meta object ID.
    Running the script twice for the same meta_campaign_id produces the same UUIDs.
    """
    return uuid.uuid5(_NS, f"{prefix}:{meta_id}")


# ---------------------------------------------------------------------------
# Step 1: Meta SDK initialization
# ---------------------------------------------------------------------------


def init_meta_sdk() -> tuple[AdAccount, str]:
    """Initialize the facebook-business SDK using MVP env var credentials.
    Returns (AdAccount instance, access_token).
    """
    creds = get_meta_credentials()
    session = FacebookSession(
        app_id=settings.META_APP_ID,
        app_secret=settings.META_APP_SECRET,
        access_token=creds.access_token,
    )
    api = FacebookAdsApi(session)
    account = AdAccount(creds.ad_account_id, api=api)
    return account, creds.access_token


# ---------------------------------------------------------------------------
# Step 2: Fetch all data from Meta
# ---------------------------------------------------------------------------


def fetch_campaigns(account: AdAccount) -> list[dict]:
    """Fetch all campaigns (ACTIVE + PAUSED) from the ad account."""
    logger.info("Fetching campaigns from Meta...")
    campaigns = account.get_campaigns(
        fields=[
            MetaCampaign.Field.id,
            MetaCampaign.Field.name,
            MetaCampaign.Field.status,
            MetaCampaign.Field.objective,
            MetaCampaign.Field.special_ad_categories,
            MetaCampaign.Field.created_time,
            MetaCampaign.Field.updated_time,
            MetaCampaign.Field.daily_budget,
        ],
        params={
            "effective_status": [
                "ACTIVE",
                "PAUSED",
                "CAMPAIGN_PAUSED",
                "ADSET_PAUSED",
            ],
            "limit": 100,
        },
    )
    result = [dict(c) for c in campaigns]
    for c in result:
        logger.info("  Campaign: %s (ID: %s, Status: %s)", c.get("name"), c["id"], c.get("status"))
    logger.info("Found %d campaigns", len(result))
    return result


def fetch_adsets(account: AdAccount) -> list[dict]:
    """Fetch all ad sets with targeting data."""
    logger.info("Fetching ad sets from Meta...")
    adsets = account.get_ad_sets(
        fields=[
            MetaAdSet.Field.id,
            MetaAdSet.Field.name,
            MetaAdSet.Field.campaign_id,
            MetaAdSet.Field.status,
            MetaAdSet.Field.targeting,
            MetaAdSet.Field.daily_budget,
            MetaAdSet.Field.billing_event,
            MetaAdSet.Field.optimization_goal,
            MetaAdSet.Field.destination_type,
            MetaAdSet.Field.promoted_object,
            MetaAdSet.Field.created_time,
        ],
        params={
            "effective_status": [
                "ACTIVE",
                "PAUSED",
                "CAMPAIGN_PAUSED",
                "ADSET_PAUSED",
            ],
            "limit": 100,
        },
    )
    result = [dict(a) for a in adsets]
    for a in result:
        logger.info("  AdSet: %s (ID: %s, Campaign: %s)", a.get("name"), a["id"], a.get("campaign_id"))
    logger.info("Found %d ad sets", len(result))
    return result


def fetch_ads(account: AdAccount) -> list[dict]:
    """Fetch all ads with creative references."""
    logger.info("Fetching ads from Meta...")
    ads = account.get_ads(
        fields=[
            MetaAd.Field.id,
            MetaAd.Field.name,
            MetaAd.Field.adset_id,
            MetaAd.Field.campaign_id,
            MetaAd.Field.status,
            MetaAd.Field.creative,
            MetaAd.Field.created_time,
            MetaAd.Field.updated_time,
        ],
        params={
            "effective_status": [
                "ACTIVE",
                "PAUSED",
                "CAMPAIGN_PAUSED",
                "ADSET_PAUSED",
            ],
            "limit": 100,
        },
    )
    result = [dict(a) for a in ads]
    for a in result:
        logger.info("  Ad: %s (ID: %s, AdSet: %s)", a.get("name"), a["id"], a.get("adset_id"))
    logger.info("Found %d ads", len(result))
    return result


def fetch_creative_details(creative_id: str, api) -> dict:
    """Fetch full creative details for one ad creative."""
    creative = MetaAdCreative(creative_id, api=api)
    data = creative.api_get(
        fields=[
            MetaAdCreative.Field.id,
            MetaAdCreative.Field.name,
            MetaAdCreative.Field.body,
            MetaAdCreative.Field.title,
            MetaAdCreative.Field.image_url,
            MetaAdCreative.Field.image_hash,
            MetaAdCreative.Field.thumbnail_url,
            MetaAdCreative.Field.object_story_spec,
        ]
    )
    return dict(data)


def fetch_ad_insights(ad_id: str, api, days: int = 30) -> list[dict]:
    """Fetch daily insights for one ad for the last N days."""
    ad = MetaAd(ad_id, api=api)
    try:
        insights = ad.get_insights(
            fields=[
                "impressions",
                "clicks",
                "spend",
                "actions",
                "ctr",
                "cpc",
                "cost_per_action_type",
            ],
            params={
                "time_range": {
                    "since": (date.today() - timedelta(days=days)).isoformat(),
                    "until": date.today().isoformat(),
                },
                "time_increment": 1,
                "limit": 100,
            },
        )
        result = [dict(row) for row in insights]
        logger.info("  Ad %s: %d days of insights", ad_id, len(result))
        return result
    except Exception as e:
        logger.warning("  Could not fetch insights for ad %s: %s", ad_id, e)
        return []


# ---------------------------------------------------------------------------
# Step 3: Transform Meta data into local format
# ---------------------------------------------------------------------------


def extract_target_audience(targeting: dict) -> dict:
    """Convert Meta targeting spec back to our proposal target_audience format."""
    result = {
        "age_min": targeting.get("age_min", 18),
        "age_max": targeting.get("age_max", 65),
        "genders": [],
        "interests": [],
        "locations": [],
    }

    meta_genders = targeting.get("genders", [])
    result["genders"] = [GENDER_REVERSE_MAP.get(g, "all") for g in meta_genders] or ["all"]

    for spec in targeting.get("flexible_spec", []):
        for interest in spec.get("interests", []):
            name = interest.get("name", "")
            if name:
                result["interests"].append(name)

    geo = targeting.get("geo_locations", {})

    for city in geo.get("cities", []):
        result["locations"].append({
            "type": "city",
            "name": city.get("name", "Unknown"),
            "region": city.get("region", ""),
            "country_code": city.get("country_code", "CO"),
        })

    if not result["locations"]:
        for country in geo.get("countries", []):
            result["locations"].append({"type": "country", "country_code": country})

    if not result["locations"]:
        result["locations"] = [{"type": "country", "country_code": "CO"}]

    return result


def extract_copy_from_creative(creative: dict) -> str:
    """Extract the ad copy text from creative data."""
    body = creative.get("body", "")
    if body:
        return body

    oss = creative.get("object_story_spec", {})
    link_data = oss.get("link_data", {})
    message = link_data.get("message", "")
    if message:
        return message

    return creative.get("name", "Recovered campaign")


def extract_conversions(actions: list | None) -> int:
    """Extract conversion count from Meta's actions array.
    Uses the same action types as meta_insights_service.py.
    """
    if not actions:
        return 0

    total = 0
    for action in actions:
        if action.get("action_type") in MESSAGING_ACTION_TYPES:
            total += int(action.get("value", 0))

    if total > 0:
        return total

    # Fallback: link clicks
    for action in actions:
        if action.get("action_type") == "link_click":
            return int(action.get("value", 0))

    return 0


def meta_status_to_campaign(meta_status: str) -> str:
    """Map Meta status to campaign_schema.campaigns.status."""
    return {
        "ACTIVE": "published",
        "PAUSED": "paused",
        "CAMPAIGN_PAUSED": "paused",
        "ADSET_PAUSED": "paused",
    }.get(meta_status, "published")


def meta_status_to_publication(meta_status: str) -> str:
    """Map Meta status to publishing_schema.publications.status."""
    return {
        "ACTIVE": "active",
        "PAUSED": "paused",
        "CAMPAIGN_PAUSED": "paused",
        "ADSET_PAUSED": "paused",
    }.get(meta_status, "active")


def parse_meta_datetime(time_str: str | None) -> datetime:
    """Parse Meta's datetime string into a Python datetime."""
    if not time_str:
        return datetime.now(tz=None)
    try:
        cleaned = time_str.replace("+0000", "+00:00").replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except (ValueError, AttributeError):
        return datetime.now(tz=None)


# ---------------------------------------------------------------------------
# Step 4: Write to database
# ---------------------------------------------------------------------------


async def ensure_ad_account(session: AsyncSession, access_token: str) -> uuid.UUID:
    """Ensure an ad_account record exists for the owner's MVP credentials.
    Publications have a non-nullable FK to ad_accounts, so we need one.
    Returns the ad_account UUID.
    """
    creds = get_meta_credentials()
    row = await session.execute(
        text("""
            SELECT id FROM publishing_schema.ad_accounts
            WHERE user_id = :user_id AND meta_ad_account_id = :account_id AND is_active = true
            LIMIT 1
        """),
        {"user_id": OWNER_USER_ID, "account_id": creds.ad_account_id},
    )
    existing = row.scalar_one_or_none()
    if existing:
        logger.info("Using existing ad_account: %s", existing)
        return existing

    ad_account_uuid = uuid.uuid4()
    encrypted_token = encrypt_token(access_token)
    await session.execute(
        text("""
            INSERT INTO publishing_schema.ad_accounts
            (id, user_id, meta_ad_account_id, meta_page_id, whatsapp_phone_number,
             access_token_encrypted, token_scopes, is_active)
            VALUES (:id, :user_id, :account_id, :page_id, :whatsapp,
                    :token, :scopes, true)
        """),
        {
            "id": str(ad_account_uuid),
            "user_id": OWNER_USER_ID,
            "account_id": creds.ad_account_id,
            "page_id": creds.page_id,
            "whatsapp": creds.whatsapp_number or None,
            "token": encrypted_token,
            "scopes": json.dumps([
                "ads_management", "ads_read", "business_management",
                "pages_manage_ads", "pages_read_engagement",
                "pages_show_list", "whatsapp_business_management",
                "whatsapp_business_messaging",
            ]),
        },
    )
    logger.info("Created ad_account: %s", ad_account_uuid)
    return ad_account_uuid


async def write_to_database(
    meta_campaigns: list[dict],
    meta_adsets: list[dict],
    meta_ads: list[dict],
    creatives: dict[str, dict],
    insights: dict[str, list[dict]],
    access_token: str,
):
    """Write all recovered data to the three database schemas."""
    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Build lookups: meta_campaign_id -> first adset/ad for that campaign
    adset_by_campaign: dict[str, dict] = {}
    for adset in meta_adsets:
        cid = adset.get("campaign_id", "")
        if cid not in adset_by_campaign:
            adset_by_campaign[cid] = adset

    ad_by_campaign: dict[str, dict] = {}
    for ad in meta_ads:
        cid = ad.get("campaign_id", "")
        if cid not in ad_by_campaign:
            ad_by_campaign[cid] = ad

    recovered = 0
    skipped = 0

    creds = get_meta_credentials()

    async with session_factory() as session:
        # Ensure we have an ad_account for the FK
        ad_account_uuid = await ensure_ad_account(session, access_token)
        await session.commit()

        for mc in meta_campaigns:
            meta_campaign_id = mc["id"]
            campaign_name = mc.get("name", "Recovered campaign")
            meta_status = mc.get("status", "ACTIVE")
            created_time = mc.get("created_time")

            # Idempotency: check if this meta campaign was already recovered
            exists = await session.execute(
                text("SELECT id FROM publishing_schema.publications WHERE meta_campaign_id = :mcid"),
                {"mcid": meta_campaign_id},
            )
            if exists.scalar_one_or_none():
                logger.info("  SKIP (already exists): %s (%s)", campaign_name, meta_campaign_id)
                skipped += 1
                continue

            adset = adset_by_campaign.get(meta_campaign_id, {})
            ad = ad_by_campaign.get(meta_campaign_id, {})
            ad_id = ad.get("id", "")
            creative_data = creatives.get(ad_id, {})
            ad_insights = insights.get(ad_id, [])

            targeting = adset.get("targeting", {})
            target_audience = extract_target_audience(targeting)
            copy_text = extract_copy_from_creative(creative_data)
            created_at = parse_meta_datetime(created_time)

            # Deterministic UUIDs: re-running produces the same PKs for the same Meta campaign
            campaign_uuid = deterministic_uuid("campaign", meta_campaign_id)
            proposal_uuid = deterministic_uuid("proposal", meta_campaign_id)
            publication_uuid = deterministic_uuid("publication", meta_campaign_id)

            local_status = meta_status_to_campaign(meta_status)
            pub_status = meta_status_to_publication(meta_status)

            # Budget: adset daily_budget is in centavos (smallest currency unit)
            daily_budget = int(adset.get("daily_budget", 0) or mc.get("daily_budget", 0) or 0)

            logger.info("  RECOVERING: %s (Meta ID: %s)", campaign_name, meta_campaign_id)
            logger.info("    Status: %s -> %s | Budget: %d cents/day", meta_status, local_status, daily_budget)

            # Use a savepoint so one campaign's failure doesn't roll back the rest
            try:
                async with session.begin_nested():
                    # --- 1. Campaign ---
                    await session.execute(text("""
                        INSERT INTO campaign_schema.campaigns
                        (id, user_id, user_prompt, status, selected_proposal_id, created_at, updated_at)
                        VALUES (:id, :user_id, :prompt, :status, :proposal_id, :created_at, :created_at)
                        ON CONFLICT (id) DO NOTHING
                    """), {
                        "id": str(campaign_uuid),
                        "user_id": OWNER_USER_ID,
                        "prompt": f"[Recovered from Meta] {campaign_name}",
                        "status": local_status,
                        "proposal_id": str(proposal_uuid),
                        "created_at": created_at,
                    })

                    # --- 2. Proposal ---
                    image_url = creative_data.get("image_url") or creative_data.get("thumbnail_url")

                    await session.execute(text("""
                        INSERT INTO campaign_schema.proposals
                        (id, campaign_id, copy_text, script, image_prompt, target_audience,
                         cta_type, whatsapp_number, is_selected, is_edited, image_url, created_at)
                        VALUES (:id, :campaign_id, :copy_text, :script, :image_prompt, :target_audience,
                                :cta_type, :whatsapp_number, true, false, :image_url, :created_at)
                        ON CONFLICT (id) DO NOTHING
                    """), {
                        "id": str(proposal_uuid),
                        "campaign_id": str(campaign_uuid),
                        "copy_text": copy_text,
                        "script": "",
                        "image_prompt": "[Recovered from Meta]",
                        "target_audience": json.dumps(target_audience),
                        "cta_type": "whatsapp_chat",
                        "whatsapp_number": creds.whatsapp_number or None,
                        "image_url": image_url,
                        "created_at": created_at,
                    })

                    # --- 3. Publication (with ad_account_id FK) ---
                    meta_adset_id = adset.get("id")
                    creative_ref = ad.get("creative", {})
                    meta_adcreative_id = creative_data.get("id") or (creative_ref.get("id") if isinstance(creative_ref, dict) else None)
                    meta_image_hash = creative_data.get("image_hash")

                    await session.execute(text("""
                        INSERT INTO publishing_schema.publications
                        (id, campaign_id, proposal_id, ad_account_id,
                         meta_campaign_id, meta_adset_id, meta_adcreative_id, meta_ad_id, meta_image_hash,
                         destination_type, campaign_objective, status, budget_daily_cents,
                         published_at, created_at, special_ad_categories, resolved_geo_locations)
                        VALUES (:id, :campaign_id, :proposal_id, :ad_account_id,
                                :meta_campaign_id, :meta_adset_id, :meta_adcreative_id, :meta_ad_id, :meta_image_hash,
                                :destination_type, :campaign_objective, :status, :budget,
                                :published_at, :created_at, :special_ad_categories, :resolved_geo_locations)
                        ON CONFLICT (id) DO NOTHING
                    """), {
                        "id": str(publication_uuid),
                        "campaign_id": str(campaign_uuid),
                        "proposal_id": str(proposal_uuid),
                        "ad_account_id": str(ad_account_uuid),
                        "meta_campaign_id": meta_campaign_id,
                        "meta_adset_id": meta_adset_id,
                        "meta_adcreative_id": meta_adcreative_id,
                        "meta_ad_id": ad_id or None,
                        "meta_image_hash": meta_image_hash,
                        "destination_type": adset.get("destination_type", "WHATSAPP"),
                        "campaign_objective": mc.get("objective", "OUTCOME_ENGAGEMENT"),
                        "status": pub_status,
                        "budget": daily_budget,
                        "published_at": created_at,
                        "created_at": created_at,
                        "special_ad_categories": json.dumps(mc.get("special_ad_categories", [])),
                        "resolved_geo_locations": json.dumps(targeting.get("geo_locations", {})),
                    })

                    # --- 4. Campaign owner in analytics_schema ---
                    await session.execute(text("""
                        INSERT INTO analytics_schema.campaign_owners (campaign_id, user_id)
                        VALUES (:campaign_id, :user_id)
                        ON CONFLICT (campaign_id) DO NOTHING
                    """), {
                        "campaign_id": str(campaign_uuid),
                        "user_id": OWNER_USER_ID,
                    })

                    # --- 5. Metric rows (only if we have a real ad_id) ---
                    metrics_count = 0
                    if ad_id:
                        for day_data in ad_insights:
                            day_date = day_data.get("date_start", date.today().isoformat())
                            impressions = int(day_data.get("impressions", 0))
                            clicks = int(day_data.get("clicks", 0))

                            # Meta returns spend as string in account currency (e.g. "23.50")
                            spend_cents = int(round(float(day_data.get("spend", "0")) * 100))
                            ctr = float(day_data.get("ctr", 0) or 0)
                            cpc_cents = int(round(float(day_data.get("cpc", "0") or 0) * 100))
                            conversions = extract_conversions(day_data.get("actions"))

                            await session.execute(text("""
                                INSERT INTO analytics_schema.campaign_metrics
                                (id, campaign_id, meta_ad_id, date, impressions, clicks,
                                 spend_cents, conversions, ctr, cpc_cents, roas)
                                VALUES (:id, :campaign_id, :meta_ad_id, :date, :impressions, :clicks,
                                        :spend_cents, :conversions, :ctr, :cpc_cents, :roas)
                                ON CONFLICT (meta_ad_id, date) DO NOTHING
                            """), {
                                "id": str(uuid.uuid4()),
                                "campaign_id": str(campaign_uuid),
                                "meta_ad_id": ad_id,
                                "date": day_date,
                                "impressions": impressions,
                                "clicks": clicks,
                                "spend_cents": spend_cents,
                                "conversions": conversions,
                                "ctr": round(ctr, 4),
                                "cpc_cents": cpc_cents,
                                "roas": 0.0,
                            })
                            metrics_count += 1

                # Savepoint succeeded — commit this campaign
                await session.commit()
                recovered += 1
                logger.info(
                    "    OK: campaign=%s, proposal=%s, publication=%s, metrics=%d days",
                    campaign_uuid, proposal_uuid, publication_uuid, metrics_count,
                )

            except Exception as e:
                logger.error("    FAILED to recover %s: %s", campaign_name, e)
                # Savepoint was rolled back; continue with the next campaign

    await engine.dispose()
    return recovered, skipped


# ---------------------------------------------------------------------------
# Step 5: Main entry point
# ---------------------------------------------------------------------------


async def main():
    logger.info("=" * 60)
    logger.info("META ADS RECOVERY SCRIPT")
    logger.info("=" * 60)

    # Initialize Meta SDK
    account, access_token = init_meta_sdk()
    creds = get_meta_credentials()
    logger.info("Connected to Meta Ad Account: %s", creds.ad_account_id)

    # Fetch all data from Meta (sync calls — SDK is synchronous)
    meta_campaigns = fetch_campaigns(account)
    meta_adsets = fetch_adsets(account)
    meta_ads = fetch_ads(account)

    if not meta_campaigns:
        logger.warning("No campaigns found in Meta. Nothing to recover.")
        return

    # Fetch creative details for each ad
    logger.info("Fetching creative details...")
    creatives: dict[str, dict] = {}
    for ad in meta_ads:
        ad_id = ad.get("id", "")
        creative_ref = ad.get("creative", {})
        creative_id = creative_ref.get("id", "") if isinstance(creative_ref, dict) else ""
        if creative_id:
            try:
                creatives[ad_id] = fetch_creative_details(creative_id, account.get_api_assured())
                logger.info("  Creative for ad %s: %s", ad_id, creative_id)
            except Exception as e:
                logger.warning("  Could not fetch creative %s: %s", creative_id, e)
                creatives[ad_id] = {}

    # Fetch insights for each ad (last 30 days)
    logger.info("Fetching insights (last 30 days)...")
    insights: dict[str, list[dict]] = {}
    for ad in meta_ads:
        ad_id = ad.get("id", "")
        if ad_id:
            insights[ad_id] = fetch_ad_insights(ad_id, account.get_api_assured(), days=30)

    # Write to database
    logger.info("Writing to database...")
    recovered, skipped = await write_to_database(
        meta_campaigns, meta_adsets, meta_ads, creatives, insights, access_token,
    )

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("RECOVERY SUMMARY")
    logger.info("  Campaigns recovered: %d", recovered)
    logger.info("  Campaigns skipped:   %d (already in DB)", skipped)
    logger.info("  Meta campaigns:      %d", len(meta_campaigns))
    logger.info("  Meta ad sets:        %d", len(meta_adsets))
    logger.info("  Meta ads:            %d", len(meta_ads))
    logger.info("  Creatives fetched:   %d", len(creatives))
    logger.info("  Ads with insights:   %d", len([v for v in insights.values() if v]))
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
