import uuid
from datetime import date

import pytest

from app.models.metric import CampaignMetric, CampaignOwner
from app.services.analytics_service import AnalyticsService
from tests.conftest import MOCK_USER


@pytest.mark.asyncio
async def test_store_metrics_insert(db_session):
    campaign_id = uuid.uuid4()
    meta_ad_id = "store_insert_1"
    metrics = [
        {
            "date": date.today().isoformat(),
            "impressions": 1000,
            "clicks": 50,
            "spend_cents": 2500,
            "conversions": 5,
            "ctr": 5.0,
            "cpc_cents": 50,
            "roas": 0.0,
        }
    ]

    service = AnalyticsService(db_session)
    count = await service.store_metrics(campaign_id, meta_ad_id, metrics)
    await db_session.commit()

    assert count == 1

    from sqlalchemy import select
    result = await db_session.execute(
        select(CampaignMetric).where(CampaignMetric.meta_ad_id == meta_ad_id)
    )
    row = result.scalar_one()
    assert row.impressions == 1000
    assert row.clicks == 50
    assert row.spend_cents == 2500


@pytest.mark.asyncio
async def test_store_metrics_upsert(db_session):
    campaign_id = uuid.uuid4()
    meta_ad_id = "upsert_test_1"
    today = date.today().isoformat()

    service = AnalyticsService(db_session)

    # First insert
    metrics_v1 = [
        {
            "date": today,
            "impressions": 500,
            "clicks": 25,
            "spend_cents": 1000,
            "conversions": 3,
            "ctr": 5.0,
            "cpc_cents": 40,
            "roas": 0.0,
        }
    ]
    await service.store_metrics(campaign_id, meta_ad_id, metrics_v1)
    await db_session.commit()

    # Upsert with updated values
    metrics_v2 = [
        {
            "date": today,
            "impressions": 1000,
            "clicks": 60,
            "spend_cents": 2500,
            "conversions": 8,
            "ctr": 6.0,
            "cpc_cents": 42,
            "roas": 1.5,
        }
    ]
    await service.store_metrics(campaign_id, meta_ad_id, metrics_v2)
    await db_session.commit()

    from sqlalchemy import select
    result = await db_session.execute(
        select(CampaignMetric).where(CampaignMetric.meta_ad_id == meta_ad_id)
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].impressions == 1000
    assert rows[0].clicks == 60
    assert rows[0].spend_cents == 2500


@pytest.mark.asyncio
async def test_get_summary_aggregation(db_session):
    user_id = MOCK_USER["user_id"]
    c1 = uuid.uuid4()
    c2 = uuid.uuid4()

    service = AnalyticsService(db_session)

    # Set up owners
    await service.ensure_campaign_owner(c1, user_id)
    await service.ensure_campaign_owner(c2, user_id)
    await db_session.commit()

    # Store metrics
    await service.store_metrics(c1, "sum_ad_1", [
        {"date": date.today().isoformat(), "impressions": 100, "clicks": 10,
         "spend_cents": 500, "conversions": 2, "ctr": 10.0, "cpc_cents": 50, "roas": 1.0},
    ])
    await service.store_metrics(c2, "sum_ad_2", [
        {"date": date.today().isoformat(), "impressions": 200, "clicks": 20,
         "spend_cents": 1000, "conversions": 4, "ctr": 10.0, "cpc_cents": 50, "roas": 2.0},
    ])
    await db_session.commit()

    summary = await service.get_summary(user_id)
    assert summary["total_impressions"] == 300
    assert summary["total_clicks"] == 30
    assert summary["total_spend_cents"] == 1500
    assert summary["total_conversions"] == 6
    assert summary["active_campaigns"] == 2
