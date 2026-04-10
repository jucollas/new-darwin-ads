import pytest
from unittest.mock import patch, MagicMock


pytestmark = pytest.mark.asyncio


class TestPublicationEndpoints:
    """Tests for publication CRUD endpoints."""

    async def _create_ad_account(self, client) -> str:
        """Helper to create an ad account and return its ID."""
        resp = await client.post(
            "/api/v1/publish/ad-accounts",
            json={
                "meta_ad_account_id": "act_pub_test",
                "meta_page_id": "page_001",
                "access_token": "EAAtoken_pub",
                "whatsapp_phone_number": "+573001234567",
            },
        )
        return resp.json()["id"]

    @patch("shared.celery_app.config.celery_app")
    async def test_create_publication_success(self, mock_celery, client):
        mock_celery.send_task = MagicMock()
        account_id = await self._create_ad_account(client)

        response = await client.post(
            "/api/v1/publish/",
            json={
                "campaign_id": "00000000-0000-0000-0000-000000000001",
                "proposal_id": "00000000-0000-0000-0000-000000000002",
                "ad_account_id": account_id,
                "budget_daily_cents": 5000,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "queued"
        assert data["budget_daily_cents"] == 5000
        assert data["destination_type"] == "WHATSAPP"
        assert data["campaign_objective"] == "OUTCOME_ENGAGEMENT"
        assert data["special_ad_categories"] == []
        mock_celery.send_task.assert_called_once()

    async def test_create_publication_invalid_account(self, client):
        response = await client.post(
            "/api/v1/publish/",
            json={
                "campaign_id": "00000000-0000-0000-0000-000000000001",
                "proposal_id": "00000000-0000-0000-0000-000000000002",
                "ad_account_id": "00000000-0000-0000-0000-000000000099",
                "budget_daily_cents": 5000,
            },
        )
        assert response.status_code == 400

    async def test_create_publication_zero_budget(self, client):
        response = await client.post(
            "/api/v1/publish/",
            json={
                "campaign_id": "00000000-0000-0000-0000-000000000001",
                "proposal_id": "00000000-0000-0000-0000-000000000002",
                "ad_account_id": "00000000-0000-0000-0000-000000000001",
                "budget_daily_cents": 0,
            },
        )
        assert response.status_code == 422

    async def test_create_publication_budget_below_minimum(self, client):
        """Budget below $1 USD (100 cents) should be rejected."""
        response = await client.post(
            "/api/v1/publish/",
            json={
                "campaign_id": "00000000-0000-0000-0000-000000000001",
                "proposal_id": "00000000-0000-0000-0000-000000000002",
                "ad_account_id": "00000000-0000-0000-0000-000000000001",
                "budget_daily_cents": 50,
            },
        )
        assert response.status_code == 422

    async def test_create_publication_invalid_objective(self, client):
        response = await client.post(
            "/api/v1/publish/",
            json={
                "campaign_id": "00000000-0000-0000-0000-000000000001",
                "proposal_id": "00000000-0000-0000-0000-000000000002",
                "ad_account_id": "00000000-0000-0000-0000-000000000001",
                "budget_daily_cents": 5000,
                "campaign_objective": "INVALID_OBJECTIVE",
            },
        )
        assert response.status_code == 422

    async def test_list_publications_empty(self, client):
        response = await client.get("/api/v1/publish/publications")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @patch("shared.celery_app.config.celery_app")
    async def test_list_publications_with_data(self, mock_celery, client):
        mock_celery.send_task = MagicMock()
        account_id = await self._create_ad_account(client)

        await client.post(
            "/api/v1/publish/",
            json={
                "campaign_id": "00000000-0000-0000-0000-000000000001",
                "proposal_id": "00000000-0000-0000-0000-000000000002",
                "ad_account_id": account_id,
                "budget_daily_cents": 3000,
            },
        )

        response = await client.get("/api/v1/publish/publications")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 1

    async def test_get_publication_status_not_found(self, client):
        response = await client.get(
            "/api/v1/publish/publications/00000000-0000-0000-0000-000000000000/status"
        )
        assert response.status_code == 404

    async def test_pause_publication_not_found(self, client):
        response = await client.post(
            "/api/v1/publish/publications/00000000-0000-0000-0000-000000000000/pause"
        )
        assert response.status_code == 400

    async def test_resume_publication_not_found(self, client):
        response = await client.post(
            "/api/v1/publish/publications/00000000-0000-0000-0000-000000000000/resume"
        )
        assert response.status_code == 400

    async def test_delete_publication_not_found(self, client):
        response = await client.delete(
            "/api/v1/publish/publications/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404
