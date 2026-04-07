import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.models.genetic import GeneticConfig, OptimizationRun
from app.services.optimizer import OptimizationOrchestrator
from app.schemas.genetic import CampaignEvaluation

from tests.conftest import MOCK_USER


def _make_campaign_data(campaign_id=None, status="published"):
    cid = str(campaign_id or uuid.uuid4())
    return {"id": cid, "status": status, "user_id": MOCK_USER["user_id"]}


def _make_publication_data(campaign_id, pub_id=None):
    return {
        "id": str(pub_id or uuid.uuid4()),
        "campaign_id": str(campaign_id),
        "meta_ad_id": f"meta_{uuid.uuid4().hex[:8]}",
        "budget_daily_cents": 500,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    }


def _make_metrics_data(days=10):
    return [
        {
            "impressions": 500,
            "clicks": 10,
            "spend_cents": 300,
            "conversions": 2,
            "ctr": 0.02,
            "cpc_cents": 30,
            "roas": 4.0,
        }
        for _ in range(days)
    ]


@pytest.mark.asyncio
class TestOptimizationOrchestrator:
    async def test_full_cycle_happy_path(self, db_session):
        orchestrator = OptimizationOrchestrator(db_session)

        campaign_ids = [uuid.uuid4() for _ in range(5)]
        campaigns = [_make_campaign_data(cid) for cid in campaign_ids]
        publications = [_make_publication_data(cid) for cid in campaign_ids]
        metrics = _make_metrics_data(10)

        with patch.object(
            orchestrator.evaluation_service,
            "fetch_published_campaigns",
            new_callable=AsyncMock,
            return_value=campaigns,
        ), patch.object(
            orchestrator.evaluation_service,
            "fetch_publications",
            new_callable=AsyncMock,
            return_value=publications,
        ), patch.object(
            orchestrator.evaluation_service,
            "fetch_metrics",
            new_callable=AsyncMock,
            return_value=metrics,
        ), patch.object(
            orchestrator.mutation_service,
            "mutate_proposal",
            new_callable=AsyncMock,
            return_value={"copy_text": "mutated", "script": "s", "image_prompt": "p", "target_audience": {}},
        ), patch.object(
            orchestrator,
            "_execute_kill",
            new_callable=AsyncMock,
            return_value=True,
        ), patch.object(
            orchestrator,
            "_fetch_proposal",
            new_callable=AsyncMock,
            return_value={"copy_text": "original", "script": "s", "image_prompt": "p", "target_audience": {}},
        ), patch.object(
            orchestrator,
            "_create_campaign",
            new_callable=AsyncMock,
            return_value=uuid.uuid4(),
        ), patch(
            "app.services.optimizer.celery_app"
        ) as mock_celery:
            run = await orchestrator.run_optimization(MOCK_USER["user_id"])

            assert isinstance(run, OptimizationRun)
            assert run.generation_number == 1
            assert run.user_id == MOCK_USER["user_id"]

    async def test_full_cycle_no_campaigns(self, db_session):
        orchestrator = OptimizationOrchestrator(db_session)

        with patch.object(
            orchestrator.evaluation_service,
            "fetch_published_campaigns",
            new_callable=AsyncMock,
            return_value=[],
        ), patch.object(
            orchestrator.evaluation_service,
            "fetch_publications",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "app.services.optimizer.celery_app"
        ):
            run = await orchestrator.run_optimization(MOCK_USER["user_id"])
            assert run.campaigns_evaluated == 0
            assert run.campaigns_killed == []
            assert run.campaigns_duplicated == []

    async def test_full_cycle_all_immature(self, db_session):
        orchestrator = OptimizationOrchestrator(db_session)

        campaign_ids = [uuid.uuid4() for _ in range(3)]
        campaigns = [_make_campaign_data(cid) for cid in campaign_ids]
        publications = [_make_publication_data(cid) for cid in campaign_ids]
        # Very few metrics — campaigns are immature
        metrics = [
            {
                "impressions": 50,
                "clicks": 1,
                "spend_cents": 10,
                "conversions": 0,
                "ctr": 0.02,
                "cpc_cents": 10,
                "roas": 0.0,
            }
        ]

        with patch.object(
            orchestrator.evaluation_service,
            "fetch_published_campaigns",
            new_callable=AsyncMock,
            return_value=campaigns,
        ), patch.object(
            orchestrator.evaluation_service,
            "fetch_publications",
            new_callable=AsyncMock,
            return_value=publications,
        ), patch.object(
            orchestrator.evaluation_service,
            "fetch_metrics",
            new_callable=AsyncMock,
            return_value=metrics,
        ), patch(
            "app.services.optimizer.celery_app"
        ):
            run = await orchestrator.run_optimization(MOCK_USER["user_id"])
            # All immature → 0 evaluated (they have ~50 impressions, well below 1000)
            assert run.campaigns_evaluated == 0

    async def test_auto_create_config(self, db_session):
        orchestrator = OptimizationOrchestrator(db_session)

        config = await orchestrator._get_or_create_config("new-user-123")
        assert config is not None
        assert config.user_id == "new-user-123"
        assert config.target_cpa_cents == 140

    async def test_generation_number_increments(self, db_session):
        user_id = "gen-test-user"

        # Create a previous run
        prev_run = OptimizationRun(
            user_id=user_id,
            generation_number=5,
            campaigns_evaluated=3,
            campaigns_killed=[],
            campaigns_duplicated=[],
            fitness_scores={},
        )
        db_session.add(prev_run)
        await db_session.flush()

        orchestrator = OptimizationOrchestrator(db_session)
        next_gen = await orchestrator._next_generation(user_id)
        assert next_gen == 6

    async def test_external_service_failure_graceful(self, db_session):
        orchestrator = OptimizationOrchestrator(db_session)

        campaign_ids = [uuid.uuid4() for _ in range(3)]
        campaigns = [_make_campaign_data(cid) for cid in campaign_ids]
        publications = [_make_publication_data(cid) for cid in campaign_ids]
        metrics = _make_metrics_data(10)

        with patch.object(
            orchestrator.evaluation_service,
            "fetch_published_campaigns",
            new_callable=AsyncMock,
            return_value=campaigns,
        ), patch.object(
            orchestrator.evaluation_service,
            "fetch_publications",
            new_callable=AsyncMock,
            return_value=publications,
        ), patch.object(
            orchestrator.evaluation_service,
            "fetch_metrics",
            new_callable=AsyncMock,
            return_value=metrics,
        ), patch.object(
            orchestrator,
            "_execute_kill",
            new_callable=AsyncMock,
            return_value=False,  # Kill execution fails
        ), patch.object(
            orchestrator,
            "_fetch_proposal",
            new_callable=AsyncMock,
            return_value=None,  # Proposal fetch fails
        ), patch(
            "app.services.optimizer.celery_app"
        ):
            run = await orchestrator.run_optimization(MOCK_USER["user_id"])
            # Should still complete without raising
            assert isinstance(run, OptimizationRun)

    async def test_mutation_service_failure_graceful(self, db_session):
        orchestrator = OptimizationOrchestrator(db_session)

        campaign_ids = [uuid.uuid4() for _ in range(3)]
        campaigns = [_make_campaign_data(cid) for cid in campaign_ids]
        publications = [_make_publication_data(cid) for cid in campaign_ids]
        metrics = _make_metrics_data(10)

        original_proposal = {
            "copy_text": "original",
            "script": "s",
            "image_prompt": "p",
            "target_audience": {},
        }

        with patch.object(
            orchestrator.evaluation_service,
            "fetch_published_campaigns",
            new_callable=AsyncMock,
            return_value=campaigns,
        ), patch.object(
            orchestrator.evaluation_service,
            "fetch_publications",
            new_callable=AsyncMock,
            return_value=publications,
        ), patch.object(
            orchestrator.evaluation_service,
            "fetch_metrics",
            new_callable=AsyncMock,
            return_value=metrics,
        ), patch.object(
            orchestrator,
            "_execute_kill",
            new_callable=AsyncMock,
            return_value=True,
        ), patch.object(
            orchestrator,
            "_fetch_proposal",
            new_callable=AsyncMock,
            return_value=original_proposal,
        ), patch.object(
            orchestrator.mutation_service,
            "mutate_proposal",
            new_callable=AsyncMock,
            return_value=original_proposal,  # Returns original on failure
        ), patch.object(
            orchestrator,
            "_create_campaign",
            new_callable=AsyncMock,
            return_value=uuid.uuid4(),
        ), patch(
            "app.services.optimizer.celery_app"
        ):
            run = await orchestrator.run_optimization(MOCK_USER["user_id"])
            assert isinstance(run, OptimizationRun)
