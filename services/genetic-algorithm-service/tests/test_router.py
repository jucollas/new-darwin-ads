import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.models.genetic import GeneticConfig, OptimizationRun
from tests.conftest import MOCK_USER


@pytest.mark.asyncio
class TestRouter:
    async def test_get_config_auto_creates(self, client):
        resp = await client.get("/api/v1/optimize/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == MOCK_USER["user_id"]
        assert data["target_cpa_cents"] == 140
        assert data["mutation_rate"] == 0.15

    async def test_put_config_partial_update(self, client):
        # First create config
        await client.get("/api/v1/optimize/config")

        resp = await client.put(
            "/api/v1/optimize/config",
            json={"target_cpa_cents": 200},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_cpa_cents"] == 200
        # Other fields unchanged
        assert data["mutation_rate"] == 0.15

    async def test_put_config_weight_validation(self, client):
        resp = await client.put(
            "/api/v1/optimize/config",
            json={
                "fitness_weights": {
                    "roas": 0.3,
                    "ctr": 0.2,
                    # sums to 0.5, not 1.0
                }
            },
        )
        assert resp.status_code == 422

    async def test_put_config_mutation_rate_validation(self, client):
        resp = await client.put(
            "/api/v1/optimize/config",
            json={"mutation_rate": 1.5},
        )
        assert resp.status_code == 422

    async def test_put_config_target_cpa_validation(self, client):
        resp = await client.put(
            "/api/v1/optimize/config",
            json={"target_cpa_cents": -10},
        )
        assert resp.status_code == 422

    async def test_get_optimization_runs_empty(self, client):
        resp = await client.get("/api/v1/optimize/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_get_optimization_run_not_found(self, client):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/optimize/{fake_id}")
        assert resp.status_code == 404

    async def test_post_run_optimization(self, client):
        with patch(
            "app.api.router.OptimizationOrchestrator"
        ) as MockOrchestrator:
            mock_run = OptimizationRun(
                id=uuid.uuid4(),
                user_id=MOCK_USER["user_id"],
                generation_number=1,
                campaigns_evaluated=3,
                campaigns_killed=[],
                campaigns_duplicated=[],
                fitness_scores={},
                ran_at=datetime.now(timezone.utc),
            )
            mock_instance = AsyncMock()
            mock_instance.run_optimization.return_value = mock_run
            MockOrchestrator.return_value = mock_instance

            resp = await client.post("/api/v1/optimize/")
            assert resp.status_code == 201
            data = resp.json()
            assert data["generation_number"] == 1
            assert data["campaigns_evaluated"] == 3

    async def test_health_endpoint(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "genetic-algorithm-service"
