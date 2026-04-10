import uuid
from datetime import datetime, timezone

import httpx
import structlog

from app.config import settings
from app.schemas.genetic import (
    CampaignClassification,
    CampaignEvaluation,
)
from app.models.genetic import GeneticConfig

logger = structlog.get_logger()


class EvaluationService:
    """
    Fetches campaign + publication + metrics data from other services
    via internal HTTP and aggregates them into CampaignEvaluation objects.
    """

    async def fetch_published_campaigns(self, user_id: str, token: str) -> list[dict]:
        """Fetch published and paused campaigns from campaign-service."""
        campaigns = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for status in ("published", "paused"):
                try:
                    resp = await client.get(
                        f"{settings.CAMPAIGN_SERVICE_URL}/api/v1/campaigns",
                        params={"status": status, "page_size": 100},
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    items = data.get("items", data) if isinstance(data, dict) else data
                    if isinstance(items, list):
                        campaigns.extend(items)
                    else:
                        campaigns.extend(data.get("items", []))
                except Exception as exc:
                    logger.error(
                        "fetch_campaigns_failed",
                        status=status,
                        error=str(exc),
                    )
        return campaigns

    async def fetch_publications(self, user_id: str, token: str) -> list[dict]:
        """Fetch publications from publishing-service."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{settings.PUBLISHING_SERVICE_URL}/api/v1/publish/publications",
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("items", data) if isinstance(data, dict) else data
        except Exception as exc:
            logger.error("fetch_publications_failed", error=str(exc))
            return []

    async def fetch_metrics(
        self, campaign_id: str, token: str, days: int = 30
    ) -> list[dict]:
        """Fetch daily metric rows from analytics-service."""
        from datetime import timedelta, date

        date_to = date.today().isoformat()
        date_from = (date.today() - timedelta(days=days)).isoformat()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{settings.ANALYTICS_SERVICE_URL}/api/v1/metrics/{campaign_id}",
                    params={"from_date": date_from, "to_date": date_to},
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("items", data) if isinstance(data, dict) else data
        except Exception as exc:
            logger.warning(
                "fetch_metrics_failed",
                campaign_id=campaign_id,
                error=str(exc),
            )
            return []

    async def build_evaluations(
        self, user_id: str, token: str, config: GeneticConfig | None = None
    ) -> list[CampaignEvaluation]:
        """
        Orchestrate data fetching and build CampaignEvaluation objects.
        """
        campaigns = await self.fetch_published_campaigns(user_id, token)
        publications = await self.fetch_publications(user_id, token)

        # Index publications by campaign_id — prefer active publication
        pub_by_campaign: dict[str, dict] = {}
        for pub in publications:
            cid = str(pub.get("campaign_id", ""))
            if not cid:
                continue

            pub_status = pub.get("status", "")
            existing = pub_by_campaign.get(cid)

            if existing is None:
                pub_by_campaign[cid] = pub
            elif pub_status == "active" and existing.get("status") != "active":
                pub_by_campaign[cid] = pub
            elif pub_status == "active" and existing.get("status") == "active":
                # Both active — prefer the most recently published
                if pub.get("published_at", "") > existing.get("published_at", ""):
                    pub_by_campaign[cid] = pub

        evaluations: list[CampaignEvaluation] = []

        for campaign in campaigns:
            campaign_id = str(campaign.get("id", ""))
            pub = pub_by_campaign.get(campaign_id)
            if not pub:
                logger.warning(
                    "campaign_no_publication",
                    campaign_id=campaign_id,
                )
                continue

            metrics = await self.fetch_metrics(campaign_id, token)

            # Aggregate metrics
            total_impressions = sum(m.get("impressions", 0) for m in metrics)
            total_clicks = sum(m.get("clicks", 0) for m in metrics)
            total_spend_cents = sum(m.get("spend_cents", 0) for m in metrics)
            total_conversions = sum(m.get("conversions", 0) for m in metrics)

            # Derived metrics
            ctr = total_clicks / total_impressions if total_impressions > 0 else 0.0
            cpc_cents = (
                total_spend_cents / total_clicks if total_clicks > 0 else 0.0
            )
            cost_per_conversion_cents = (
                total_spend_cents / total_conversions
                if total_conversions > 0
                else 0.0
            )
            conversion_rate = (
                total_conversions / total_clicks if total_clicks > 0 else 0.0
            )

            # Weighted average ROAS by spend
            total_roas_spend = 0.0
            total_spend_for_roas = 0.0
            for m in metrics:
                day_roas = m.get("roas", 0.0) or 0.0
                day_spend = m.get("spend_cents", 0) or 0
                if day_spend > 0:
                    total_roas_spend += day_roas * day_spend
                    total_spend_for_roas += day_spend

            roas = (total_roas_spend / total_spend_for_roas) if total_spend_for_roas > 0 else 0.0

            # WhatsApp CTWA campaigns: Meta reports ROAS=0 because conversations
            # aren't tracked as purchases. Estimate ROAS from conversions using
            # target_cpa_cents * 3 as the estimated revenue per conversation.
            if roas == 0.0 and total_conversions > 0 and total_spend_cents > 0:
                target_cpa = config.target_cpa_cents if config else 140
                estimated_revenue = total_conversions * target_cpa * 3
                roas = estimated_revenue / total_spend_cents
                logger.info(
                    "estimated_roas_whatsapp",
                    campaign_id=campaign_id,
                    estimated_roas=round(roas, 2),
                    conversions=total_conversions,
                )

            # Days active
            published_at_str = pub.get("published_at")
            if published_at_str:
                if isinstance(published_at_str, str):
                    published_at = datetime.fromisoformat(
                        published_at_str.replace("Z", "+00:00")
                    )
                else:
                    published_at = published_at_str
            else:
                published_at = datetime.now(timezone.utc)

            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)

            days_active = max(
                1, (datetime.now(timezone.utc) - published_at).days
            )

            evaluations.append(
                CampaignEvaluation(
                    campaign_id=uuid.UUID(campaign_id),
                    publication_id=uuid.UUID(str(pub.get("id", ""))),
                    meta_ad_id=pub.get("meta_ad_id", ""),
                    days_active=days_active,
                    total_impressions=total_impressions,
                    total_clicks=total_clicks,
                    total_spend_cents=total_spend_cents,
                    total_conversions=total_conversions,
                    ctr=ctr,
                    cpc_cents=cpc_cents,
                    cost_per_conversion_cents=cost_per_conversion_cents,
                    conversion_rate=conversion_rate,
                    roas=roas,
                    budget_daily_cents=pub.get("budget_daily_cents", 0),
                    status=campaign.get("status", "unknown"),
                    published_at=published_at,
                )
            )

        logger.info(
            "evaluations_built",
            user_id=user_id,
            total=len(evaluations),
        )
        return evaluations

    def classify_campaign(
        self, evaluation: CampaignEvaluation, config: GeneticConfig
    ) -> CampaignClassification:
        """
        Classify campaign maturity based on config thresholds.
        """
        if (
            evaluation.days_active < config.min_days_active
            or evaluation.total_impressions < config.min_impressions_to_evaluate
        ):
            return CampaignClassification.IMMATURE

        min_spend = config.target_cpa_cents * config.min_spend_cpa_multiplier

        if (
            evaluation.days_active >= 7
            and evaluation.total_conversions >= 50
            and evaluation.total_spend_cents >= min_spend
        ):
            return CampaignClassification.MATURE

        return CampaignClassification.EARLY_STAGE
