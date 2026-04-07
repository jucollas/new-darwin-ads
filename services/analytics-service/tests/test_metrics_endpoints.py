import uuid
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.conftest import MOCK_USER


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "analytics-service"


@pytest.mark.asyncio
async def test_get_campaign_metrics_returns_list(client):
    campaign_id = uuid.uuid4()
    user_id = MOCK_USER["user_id"]

    # Seed data via internal DB access
    from app.main import app
    from shared.database.session import get_db

    override = app.dependency_overrides[get_db]
    async for session in override():
        from app.models.metric import CampaignMetric, CampaignOwner

        session.add(CampaignOwner(campaign_id=campaign_id, user_id=user_id))
        session.add(CampaignMetric(
            id=uuid.uuid4(),
            campaign_id=campaign_id,
            meta_ad_id="123456789",
            date=date.today(),
            impressions=1500,
            clicks=45,
            spend_cents=2350,
            conversions=12,
            ctr=3.0,
            cpc_cents=52,
            roas=0.0,
        ))
        await session.commit()

    response = await client.get(f"/api/v1/metrics/{campaign_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["impressions"] == 1500
    assert data["items"][0]["clicks"] == 45
    assert data["items"][0]["spend_cents"] == 2350


@pytest.mark.asyncio
async def test_get_campaign_metrics_with_date_filter(client):
    campaign_id = uuid.uuid4()
    user_id = MOCK_USER["user_id"]

    from app.main import app
    from shared.database.session import get_db

    override = app.dependency_overrides[get_db]
    async for session in override():
        from app.models.metric import CampaignMetric, CampaignOwner

        session.add(CampaignOwner(campaign_id=campaign_id, user_id=user_id))
        today = date.today()
        # Add metric for today
        session.add(CampaignMetric(
            id=uuid.uuid4(), campaign_id=campaign_id, meta_ad_id="111",
            date=today, impressions=100, clicks=10, spend_cents=500,
            conversions=2, ctr=10.0, cpc_cents=50, roas=0.0,
        ))
        # Add metric for 10 days ago
        session.add(CampaignMetric(
            id=uuid.uuid4(), campaign_id=campaign_id, meta_ad_id="111",
            date=today - timedelta(days=10), impressions=200, clicks=20,
            spend_cents=1000, conversions=5, ctr=10.0, cpc_cents=50, roas=0.0,
        ))
        await session.commit()

    # Filter to only today
    response = await client.get(
        f"/api/v1/metrics/{campaign_id}",
        params={"from_date": date.today().isoformat(), "to_date": date.today().isoformat()},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["impressions"] == 100


@pytest.mark.asyncio
async def test_get_campaign_metrics_empty(client):
    campaign_id = uuid.uuid4()
    response = await client.get(f"/api/v1/metrics/{campaign_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_get_summary(client):
    user_id = MOCK_USER["user_id"]
    campaign_id_1 = uuid.uuid4()
    campaign_id_2 = uuid.uuid4()

    from app.main import app
    from shared.database.session import get_db

    override = app.dependency_overrides[get_db]
    async for session in override():
        from app.models.metric import CampaignMetric, CampaignOwner

        session.add(CampaignOwner(campaign_id=campaign_id_1, user_id=user_id))
        session.add(CampaignOwner(campaign_id=campaign_id_2, user_id=user_id))
        session.add(CampaignMetric(
            id=uuid.uuid4(), campaign_id=campaign_id_1, meta_ad_id="aaa",
            date=date.today(), impressions=1000, clicks=50, spend_cents=5000,
            conversions=10, ctr=5.0, cpc_cents=100, roas=2.0,
        ))
        session.add(CampaignMetric(
            id=uuid.uuid4(), campaign_id=campaign_id_2, meta_ad_id="bbb",
            date=date.today(), impressions=2000, clicks=100, spend_cents=10000,
            conversions=20, ctr=5.0, cpc_cents=100, roas=3.0,
        ))
        await session.commit()

    response = await client.get("/api/v1/metrics/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["total_impressions"] == 3000
    assert data["total_clicks"] == 150
    assert data["total_spend_cents"] == 15000
    assert data["total_conversions"] == 30
    assert data["active_campaigns"] == 2


@pytest.mark.asyncio
async def test_get_top_performers(client):
    user_id = MOCK_USER["user_id"]
    campaign_id = uuid.uuid4()

    from app.main import app
    from shared.database.session import get_db

    override = app.dependency_overrides[get_db]
    async for session in override():
        from app.models.metric import CampaignMetric, CampaignOwner

        session.add(CampaignOwner(campaign_id=campaign_id, user_id=user_id))
        session.add(CampaignMetric(
            id=uuid.uuid4(), campaign_id=campaign_id, meta_ad_id="top1",
            date=date.today(), impressions=5000, clicks=250, spend_cents=2000,
            conversions=50, ctr=5.0, cpc_cents=8, roas=10.0,
        ))
        await session.commit()

    response = await client.get("/api/v1/metrics/top-performers")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["meta_ad_id"] == "top1"


@pytest.mark.asyncio
async def test_get_underperformers(client):
    user_id = MOCK_USER["user_id"]
    campaign_id = uuid.uuid4()

    from app.main import app
    from shared.database.session import get_db

    override = app.dependency_overrides[get_db]
    async for session in override():
        from app.models.metric import CampaignMetric, CampaignOwner

        session.add(CampaignOwner(campaign_id=campaign_id, user_id=user_id))
        session.add(CampaignMetric(
            id=uuid.uuid4(), campaign_id=campaign_id, meta_ad_id="bad1",
            date=date.today(), impressions=10000, clicks=5, spend_cents=50000,
            conversions=0, ctr=0.05, cpc_cents=10000, roas=0.0,
        ))
        await session.commit()

    response = await client.get("/api/v1/metrics/underperformers")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["meta_ad_id"] == "bad1"


@pytest.mark.asyncio
async def test_collect_triggers_task(client):
    with patch("app.api.router.celery_app") as mock_celery:
        response = await client.post(
            "/api/v1/metrics/collect",
            json={"lookback_days": 7},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["lookback_days"] == 7
        mock_celery.send_task.assert_called_once()


@pytest.mark.asyncio
async def test_unauthorized_access():
    """Test that endpoints require JWT."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    # Clear overrides to test real auth
    app.dependency_overrides.clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get("/api/v1/metrics/summary")
        assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_invalid_campaign_id_format(client):
    response = await client.get("/api/v1/metrics/not-a-uuid")
    assert response.status_code == 400
