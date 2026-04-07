import uuid as _uuid
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metric import CampaignMetric, CampaignOwner


def _parse_date(value) -> date:
    """Convert a date string or date object to datetime.date."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def store_metrics(
        self, campaign_id: _uuid.UUID, meta_ad_id: str, metrics: list[dict]
    ) -> int:
        """
        Store fetched metrics using PostgreSQL ON CONFLICT upsert.
        Returns count of rows upserted.
        """
        if not metrics:
            return 0

        count = 0
        for m in metrics:
            stmt = pg_insert(CampaignMetric).values(
                id=_uuid.uuid4(),
                campaign_id=campaign_id,
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
            await self.db.execute(stmt)
            count += 1

        return count

    async def ensure_campaign_owner(
        self, campaign_id: _uuid.UUID, user_id: str
    ) -> None:
        """Ensure a campaign_owner record exists for ownership tracking."""
        stmt = pg_insert(CampaignOwner).values(
            campaign_id=campaign_id,
            user_id=user_id,
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["campaign_id"])
        await self.db.execute(stmt)

    async def get_campaign_metrics(
        self,
        campaign_id: _uuid.UUID,
        user_id: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[CampaignMetric]:
        """Query metrics for a specific campaign within optional date range."""
        # Verify campaign ownership
        owner_stmt = select(CampaignOwner).where(
            CampaignOwner.campaign_id == campaign_id,
            CampaignOwner.user_id == user_id,
        )
        owner = (await self.db.execute(owner_stmt)).scalar_one_or_none()
        if not owner:
            return []

        stmt = select(CampaignMetric).where(
            CampaignMetric.campaign_id == campaign_id
        )
        if from_date:
            stmt = stmt.where(CampaignMetric.date >= from_date)
        if to_date:
            stmt = stmt.where(CampaignMetric.date <= to_date)
        stmt = stmt.order_by(CampaignMetric.date.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_summary(
        self,
        user_id: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict:
        """Aggregate metrics across ALL campaigns for the user."""
        # Get campaign_ids owned by user
        owner_stmt = select(CampaignOwner.campaign_id).where(
            CampaignOwner.user_id == user_id
        )
        owner_result = await self.db.execute(owner_stmt)
        campaign_ids = [row[0] for row in owner_result.fetchall()]

        if not campaign_ids:
            return {
                "total_impressions": 0,
                "total_clicks": 0,
                "total_spend_cents": 0,
                "total_conversions": 0,
                "avg_ctr": 0.0,
                "avg_cpc_cents": 0.0,
                "avg_roas": 0.0,
                "active_campaigns": 0,
                "date_range_start": from_date,
                "date_range_end": to_date,
            }

        stmt = select(
            func.sum(CampaignMetric.impressions).label("total_impressions"),
            func.sum(CampaignMetric.clicks).label("total_clicks"),
            func.sum(CampaignMetric.spend_cents).label("total_spend_cents"),
            func.sum(CampaignMetric.conversions).label("total_conversions"),
            func.avg(CampaignMetric.ctr).label("avg_ctr"),
            func.avg(CampaignMetric.cpc_cents).label("avg_cpc_cents"),
            func.avg(CampaignMetric.roas).label("avg_roas"),
            func.min(CampaignMetric.date).label("date_range_start"),
            func.max(CampaignMetric.date).label("date_range_end"),
        ).where(CampaignMetric.campaign_id.in_(campaign_ids))

        if from_date:
            stmt = stmt.where(CampaignMetric.date >= from_date)
        if to_date:
            stmt = stmt.where(CampaignMetric.date <= to_date)

        result = await self.db.execute(stmt)
        row = result.one()

        # Count distinct active campaigns that have metrics
        count_stmt = select(
            func.count(func.distinct(CampaignMetric.campaign_id))
        ).where(CampaignMetric.campaign_id.in_(campaign_ids))
        if from_date:
            count_stmt = count_stmt.where(CampaignMetric.date >= from_date)
        if to_date:
            count_stmt = count_stmt.where(CampaignMetric.date <= to_date)

        count_result = await self.db.execute(count_stmt)
        active_campaigns = count_result.scalar() or 0

        return {
            "total_impressions": row.total_impressions or 0,
            "total_clicks": row.total_clicks or 0,
            "total_spend_cents": row.total_spend_cents or 0,
            "total_conversions": row.total_conversions or 0,
            "avg_ctr": round(float(row.avg_ctr or 0), 4),
            "avg_cpc_cents": round(float(row.avg_cpc_cents or 0), 2),
            "avg_roas": round(float(row.avg_roas or 0), 4),
            "active_campaigns": active_campaigns,
            "date_range_start": from_date or row.date_range_start,
            "date_range_end": to_date or row.date_range_end,
        }

    async def get_top_performers(
        self, user_id: str, limit: int = 5
    ) -> list[dict]:
        """Top campaigns by ROAS and CTR in the last 7 days."""
        owner_stmt = select(CampaignOwner.campaign_id).where(
            CampaignOwner.user_id == user_id
        )
        owner_result = await self.db.execute(owner_stmt)
        campaign_ids = [row[0] for row in owner_result.fetchall()]

        if not campaign_ids:
            return []

        seven_days_ago = date.today() - timedelta(days=7)

        stmt = (
            select(
                CampaignMetric.campaign_id,
                CampaignMetric.meta_ad_id,
                func.sum(CampaignMetric.impressions).label("impressions"),
                func.sum(CampaignMetric.clicks).label("clicks"),
                func.avg(CampaignMetric.ctr).label("ctr"),
                func.avg(CampaignMetric.roas).label("roas"),
                func.sum(CampaignMetric.spend_cents).label("spend_cents"),
            )
            .where(
                CampaignMetric.campaign_id.in_(campaign_ids),
                CampaignMetric.date >= seven_days_ago,
            )
            .group_by(CampaignMetric.campaign_id, CampaignMetric.meta_ad_id)
            .order_by(func.avg(CampaignMetric.roas).desc(), func.avg(CampaignMetric.ctr).desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return [
            {
                "campaign_id": row.campaign_id,
                "meta_ad_id": row.meta_ad_id,
                "impressions": row.impressions or 0,
                "clicks": row.clicks or 0,
                "ctr": round(float(row.ctr or 0), 4),
                "roas": round(float(row.roas or 0), 4),
                "spend_cents": row.spend_cents or 0,
            }
            for row in result.fetchall()
        ]

    async def get_underperformers(
        self, user_id: str, limit: int = 5
    ) -> list[dict]:
        """Worst campaigns by CTR and highest CPC in the last 7 days."""
        owner_stmt = select(CampaignOwner.campaign_id).where(
            CampaignOwner.user_id == user_id
        )
        owner_result = await self.db.execute(owner_stmt)
        campaign_ids = [row[0] for row in owner_result.fetchall()]

        if not campaign_ids:
            return []

        seven_days_ago = date.today() - timedelta(days=7)

        stmt = (
            select(
                CampaignMetric.campaign_id,
                CampaignMetric.meta_ad_id,
                func.sum(CampaignMetric.impressions).label("impressions"),
                func.sum(CampaignMetric.clicks).label("clicks"),
                func.avg(CampaignMetric.ctr).label("ctr"),
                func.avg(CampaignMetric.roas).label("roas"),
                func.sum(CampaignMetric.spend_cents).label("spend_cents"),
            )
            .where(
                CampaignMetric.campaign_id.in_(campaign_ids),
                CampaignMetric.date >= seven_days_ago,
            )
            .group_by(CampaignMetric.campaign_id, CampaignMetric.meta_ad_id)
            .order_by(func.avg(CampaignMetric.ctr).asc(), func.avg(CampaignMetric.cpc_cents).desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return [
            {
                "campaign_id": row.campaign_id,
                "meta_ad_id": row.meta_ad_id,
                "impressions": row.impressions or 0,
                "clicks": row.clicks or 0,
                "ctr": round(float(row.ctr or 0), 4),
                "roas": round(float(row.roas or 0), 4),
                "spend_cents": row.spend_cents or 0,
            }
            for row in result.fetchall()
        ]
