import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.tasks.celery_tasks import collect_metrics_task, _fetch_active_publications


class TestCollectMetricsTask:
    @patch("app.tasks.celery_tasks._fetch_active_publications")
    @patch("app.tasks.celery_tasks.MetaInsightsService")
    @patch("app.tasks.celery_tasks.get_sync_session")
    @patch("app.tasks.celery_tasks.celery_app")
    def test_collect_metrics_task_success(
        self, mock_celery, mock_get_session, mock_insights_cls, mock_fetch_pubs
    ):
        # Mock publications
        campaign_id = str(uuid.uuid4())
        mock_fetch_pubs.return_value = [
            {
                "campaign_id": campaign_id,
                "meta_ad_id": "ad_123",
                "status": "active",
            }
        ]

        # Mock insights service
        mock_service = MagicMock()
        mock_service.fetch_ad_insights.return_value = [
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
        mock_insights_cls.return_value = mock_service

        # Mock DB session
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        # Call task directly (not via Celery)
        result = collect_metrics_task(lookback_days=7, user_id="test-user")

        assert result["collected"] == 1
        assert result["publications"] == 1
        assert result["failed"] == 0
        mock_session.commit.assert_called()
        mock_session.close.assert_called()

    @patch("app.tasks.celery_tasks._fetch_active_publications")
    @patch("app.tasks.celery_tasks.MetaInsightsService")
    @patch("app.tasks.celery_tasks.get_sync_session")
    @patch("app.tasks.celery_tasks.celery_app")
    def test_collect_metrics_task_skips_failed_ads(
        self, mock_celery, mock_get_session, mock_insights_cls, mock_fetch_pubs
    ):
        c1 = str(uuid.uuid4())
        c2 = str(uuid.uuid4())
        mock_fetch_pubs.return_value = [
            {"campaign_id": c1, "meta_ad_id": "ad_fail", "status": "active"},
            {"campaign_id": c2, "meta_ad_id": "ad_ok", "status": "active"},
        ]

        mock_service = MagicMock()
        # First ad fails, second succeeds
        mock_service.fetch_ad_insights.side_effect = [
            Exception("Some error"),
            [{"date": date.today().isoformat(), "impressions": 100, "clicks": 5,
              "spend_cents": 500, "conversions": 1, "ctr": 5.0, "cpc_cents": 100, "roas": 0.0}],
        ]
        mock_insights_cls.return_value = mock_service

        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        result = collect_metrics_task(lookback_days=7, user_id="test-user")

        assert result["collected"] == 1
        assert result["failed"] == 1
        assert result["publications"] == 2

    @patch("app.tasks.celery_tasks._fetch_active_publications")
    @patch("app.tasks.celery_tasks.MetaInsightsService")
    @patch("app.tasks.celery_tasks.get_sync_session")
    @patch("app.tasks.celery_tasks.celery_app")
    def test_collect_metrics_task_token_expired_stops(
        self, mock_celery, mock_get_session, mock_insights_cls, mock_fetch_pubs
    ):
        from facebook_business.exceptions import FacebookRequestError

        c1 = str(uuid.uuid4())
        c2 = str(uuid.uuid4())
        mock_fetch_pubs.return_value = [
            {"campaign_id": c1, "meta_ad_id": "ad_1", "status": "active"},
            {"campaign_id": c2, "meta_ad_id": "ad_2", "status": "active"},
        ]

        token_error = FacebookRequestError(
            message="OAuthException",
            request_context={"method": "GET"},
            http_status=400,
            http_headers={},
            body='{"error": {"code": 190, "message": "Token expired"}}',
        )

        mock_service = MagicMock()
        mock_service.fetch_ad_insights.side_effect = token_error
        mock_insights_cls.return_value = mock_service

        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        result = collect_metrics_task(lookback_days=7, user_id="test-user")

        # Should stop on token expired and return early
        assert result["error"] == "token_expired"
        mock_session.commit.assert_called()

    @patch("app.tasks.celery_tasks._fetch_active_publications")
    def test_collect_metrics_no_publications(self, mock_fetch_pubs):
        mock_fetch_pubs.return_value = []
        result = collect_metrics_task(lookback_days=7)
        assert result["collected"] == 0
        assert result["publications"] == 0


class TestFetchActivePublications:
    @patch("app.tasks.celery_tasks.httpx.Client")
    def test_fetch_success(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Internal endpoint already filters by status=active
        mock_response.json.return_value = {
            "items": [
                {"campaign_id": "c1", "meta_ad_id": "ad_1", "status": "active"},
                {"campaign_id": "c2", "meta_ad_id": None, "status": "active"},
            ],
            "total": 2,
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = _fetch_active_publications()
        # Only items with meta_ad_id present
        assert len(result) == 1
        assert result[0]["meta_ad_id"] == "ad_1"

    @patch("app.tasks.celery_tasks.httpx.Client")
    def test_fetch_failure(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = Exception("Connection error")
        mock_client_cls.return_value = mock_client

        result = _fetch_active_publications()
        assert result == []
