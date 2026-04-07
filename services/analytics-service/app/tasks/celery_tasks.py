import uuid as _uuid
from datetime import date, timedelta

import httpx
import structlog
from facebook_business.exceptions import FacebookRequestError

from shared.celery_app.config import celery_app
from app.config import settings
from app.models.metric import CampaignMetric, CampaignOwner
from app.services.meta_insights_service import MetaInsightsService
from app.services.sync_db import get_sync_session

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert


def _parse_date(value) -> date:
    """Convert a date string or date object to datetime.date."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    name="tasks.analytics_collect",
    queue="analytics_tasks",
    max_retries=3,
    default_retry_delay=60,
    time_limit=600,
    soft_time_limit=540,
)
def collect_metrics_task(self, lookback_days: int = 7, user_id: str | None = None):
    """
    Collect metrics from Meta Insights API for all active publications.

    1. Fetch active publications from publishing-service
    2. For each publication with a meta_ad_id, fetch insights
    3. Store metrics in campaign_metrics table
    4. Dispatch notification on completion
    """
    logger.info(
        "collect_metrics_start",
        lookback_days=lookback_days,
        user_id=user_id,
    )

    date_to = date.today().isoformat()
    date_from = (date.today() - timedelta(days=lookback_days)).isoformat()

    # Step 1: Fetch active publications from publishing-service
    publications = _fetch_active_publications()
    if not publications:
        logger.info("collect_metrics_no_publications")
        return {"collected": 0, "publications": 0}

    # Step 2: Initialize Meta Insights service
    try:
        insights_service = MetaInsightsService(user_id=user_id)
    except Exception as exc:
        logger.error("collect_metrics_init_failed", error=str(exc))
        raise

    session = get_sync_session()
    total_upserted = 0
    failed_ads = 0

    try:
        for pub in publications:
            meta_ad_id = pub.get("meta_ad_id")
            campaign_id = pub.get("campaign_id")
            pub_user_id = user_id or "single-user"

            if not meta_ad_id or not campaign_id:
                continue

            try:
                campaign_uuid = _uuid.UUID(campaign_id)
            except ValueError:
                logger.warning("collect_metrics_invalid_campaign_id", campaign_id=campaign_id)
                continue

            # Ensure campaign ownership record
            owner_stmt = pg_insert(CampaignOwner).values(
                campaign_id=campaign_uuid,
                user_id=pub_user_id,
            )
            owner_stmt = owner_stmt.on_conflict_do_nothing(index_elements=["campaign_id"])
            session.execute(owner_stmt)

            # Fetch insights from Meta
            try:
                metrics = insights_service.fetch_ad_insights(
                    meta_ad_id, date_from, date_to
                )
            except FacebookRequestError as e:
                if e.api_error_code() == 190:
                    logger.critical(
                        "collect_metrics_token_expired",
                        meta_ad_id=meta_ad_id,
                    )
                    # Dispatch budget_alert notification and stop
                    try:
                        celery_app.send_task(
                            "tasks.notification_send",
                            queue="notification_tasks",
                            args=[pub_user_id, "budget_alert"],
                        )
                    except Exception:
                        pass
                    session.commit()
                    return {"collected": total_upserted, "error": "token_expired"}

                logger.error(
                    "collect_metrics_ad_failed",
                    meta_ad_id=meta_ad_id,
                    error=str(e),
                )
                failed_ads += 1
                continue
            except Exception as e:
                logger.error(
                    "collect_metrics_ad_error",
                    meta_ad_id=meta_ad_id,
                    error=str(e),
                )
                failed_ads += 1
                continue

            # Store metrics
            for m in metrics:
                stmt = pg_insert(CampaignMetric).values(
                    id=_uuid.uuid4(),
                    campaign_id=campaign_uuid,
                    meta_ad_id=meta_ad_id,
                    date=_parse_date(m["date"]),
                    impressions=m["impressions"],
                    clicks=m["clicks"],
                    spend_cents=m["spend_cents"],
                    conversions=m["conversions"],
                    ctr=m["ctr"],
                    cpc_cents=m["cpc_cents"],
                    roas=m["roas"],
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["meta_ad_id", "date"],
                    set_={
                        "impressions": stmt.excluded.impressions,
                        "clicks": stmt.excluded.clicks,
                        "spend_cents": stmt.excluded.spend_cents,
                        "conversions": stmt.excluded.conversions,
                        "ctr": stmt.excluded.ctr,
                        "cpc_cents": stmt.excluded.cpc_cents,
                        "roas": stmt.excluded.roas,
                        "collected_at": func.now(),
                    },
                )
                session.execute(stmt)
                total_upserted += 1

        session.commit()

        logger.info(
            "collect_metrics_complete",
            total_upserted=total_upserted,
            publications=len(publications),
            failed_ads=failed_ads,
        )

        # Dispatch notification on completion
        try:
            celery_app.send_task(
                "tasks.notification_send",
                queue="notification_tasks",
                args=[user_id or "single-user", "optimization_complete"],
            )
        except Exception:
            logger.warning("collect_metrics_notification_failed")

        return {
            "collected": total_upserted,
            "publications": len(publications),
            "failed": failed_ads,
        }

    except Exception:
        session.rollback()
        logger.exception("collect_metrics_unexpected_error")
        raise
    finally:
        session.close()


def _fetch_active_publications() -> list[dict]:
    """Fetch active publications from publishing-service via internal endpoint."""
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{settings.PUBLISHING_SERVICE_URL}/api/v1/publish/internal/publications",
                params={"status": "active"},
            )
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                return [p for p in items if p.get("meta_ad_id")]
            logger.warning(
                "fetch_publications_error",
                status_code=response.status_code,
            )
            return []
    except Exception as exc:
        logger.error("fetch_publications_failed", error=str(exc))
        return []
