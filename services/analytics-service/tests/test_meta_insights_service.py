import os
from unittest.mock import MagicMock, patch

import pytest

# Set env vars before imports
os.environ.setdefault("META_ACCESS_TOKEN", "test-token")
os.environ.setdefault("META_AD_ACCOUNT_ID", "act_123")
os.environ.setdefault("META_PAGE_ID", "page_123")
os.environ.setdefault("META_WHATSAPP_NUMBER", "+1234567890")

from app.services.meta_insights_service import MetaInsightsService


class TestParseInsight:
    def test_basic_parsing(self):
        row = {
            "ad_id": "ad_123",
            "date_start": "2025-01-15",
            "impressions": "1500",
            "clicks": "45",
            "spend": "23.50",
            "ctr": "3.0",
            "cpc": "0.52",
            "actions": [],
        }
        result = MetaInsightsService._parse_insight(row)
        assert result["meta_ad_id"] == "ad_123"
        assert result["date"] == "2025-01-15"
        assert result["impressions"] == 1500
        assert result["clicks"] == 45
        assert result["spend_cents"] == 2350
        assert result["ctr"] == 3.0
        assert result["cpc_cents"] == 52
        assert result["roas"] == 0.0

    def test_spend_conversion_to_cents(self):
        """Meta returns spend as string dollars, verify conversion to cents."""
        row = {
            "ad_id": "ad_456",
            "date_start": "2025-01-15",
            "impressions": "100",
            "clicks": "5",
            "spend": "0.99",
            "ctr": "5.0",
            "cpc": "0.20",
            "actions": [],
        }
        result = MetaInsightsService._parse_insight(row)
        assert result["spend_cents"] == 99

    def test_spend_zero(self):
        row = {
            "ad_id": "ad_789",
            "date_start": "2025-01-15",
            "impressions": "0",
            "clicks": "0",
            "spend": "0",
            "ctr": "0",
            "actions": [],
        }
        result = MetaInsightsService._parse_insight(row)
        assert result["spend_cents"] == 0
        assert result["cpc_cents"] == 0

    def test_conversions_parsing(self):
        """Verify correct action_type extraction from Meta's actions array."""
        row = {
            "ad_id": "ad_conv",
            "date_start": "2025-01-15",
            "impressions": "1000",
            "clicks": "50",
            "spend": "10.00",
            "ctr": "5.0",
            "cpc": "0.20",
            "actions": [
                {"action_type": "link_click", "value": "45"},
                {"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": "12"},
                {"action_type": "messages", "value": "8"},
                {"action_type": "page_engagement", "value": "50"},
            ],
        }
        result = MetaInsightsService._parse_insight(row)
        assert result["conversions"] == 20  # 12 + 8

    def test_no_actions(self):
        row = {
            "ad_id": "ad_no_conv",
            "date_start": "2025-01-15",
            "impressions": "500",
            "clicks": "10",
            "spend": "5.00",
            "ctr": "2.0",
            "cpc": "0.50",
        }
        result = MetaInsightsService._parse_insight(row)
        assert result["conversions"] == 0

    def test_meta_ad_id_override(self):
        """Test that explicitly passed meta_ad_id overrides row ad_id."""
        row = {
            "ad_id": "from_row",
            "date_start": "2025-01-15",
            "impressions": "100",
            "clicks": "5",
            "spend": "1.00",
            "ctr": "5.0",
            "cpc": "0.20",
            "actions": [],
        }
        result = MetaInsightsService._parse_insight(row, meta_ad_id="override_id")
        assert result["meta_ad_id"] == "override_id"


@patch("app.services.meta_insights_service.FacebookSession")
@patch("app.services.meta_insights_service.FacebookAdsApi")
class TestFetchAdInsights:
    def test_fetch_ad_insights_success(self, mock_api_cls, mock_session_cls):
        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api

        mock_insights = [
            {
                "ad_id": "ad_test",
                "date_start": "2025-01-15",
                "impressions": "1500",
                "clicks": "45",
                "spend": "23.50",
                "ctr": "3.0",
                "cpc": "0.52",
                "actions": [],
            }
        ]

        with patch("app.services.meta_insights_service.Ad") as mock_ad_cls:
            mock_ad = MagicMock()
            mock_ad.get_insights.return_value = mock_insights
            mock_ad_cls.return_value = mock_ad

            service = MetaInsightsService()
            results = service.fetch_ad_insights("ad_test", "2025-01-15", "2025-01-15")

            assert len(results) == 1
            assert results[0]["impressions"] == 1500
            assert results[0]["spend_cents"] == 2350

    def test_fetch_ad_insights_rate_limit(self, mock_api_cls, mock_session_cls):
        from facebook_business.exceptions import FacebookRequestError

        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api

        mock_error = FacebookRequestError(
            message="Rate limit hit",
            request_context={"method": "GET"},
            http_status=400,
            http_headers={},
            body='{"error": {"code": 17, "message": "Rate limit"}}',
        )

        with patch("app.services.meta_insights_service.Ad") as mock_ad_cls:
            mock_ad = MagicMock()
            mock_ad.get_insights.side_effect = mock_error
            mock_ad_cls.return_value = mock_ad

            service = MetaInsightsService()
            with patch("time.sleep"):  # Don't actually sleep in tests
                with pytest.raises(FacebookRequestError):
                    service.fetch_ad_insights("ad_test", "2025-01-15", "2025-01-15")

    def test_fetch_ad_insights_token_expired(self, mock_api_cls, mock_session_cls):
        from facebook_business.exceptions import FacebookRequestError

        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api

        mock_error = FacebookRequestError(
            message="OAuthException",
            request_context={"method": "GET"},
            http_status=400,
            http_headers={},
            body='{"error": {"code": 190, "message": "Token expired"}}',
        )

        with patch("app.services.meta_insights_service.Ad") as mock_ad_cls:
            mock_ad = MagicMock()
            mock_ad.get_insights.side_effect = mock_error
            mock_ad_cls.return_value = mock_ad

            service = MetaInsightsService()
            with pytest.raises(FacebookRequestError):
                service.fetch_ad_insights("ad_test", "2025-01-15", "2025-01-15")

    def test_fetch_ad_insights_invalid_ad(self, mock_api_cls, mock_session_cls):
        from facebook_business.exceptions import FacebookRequestError

        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api

        mock_error = FacebookRequestError(
            message="Invalid parameter",
            request_context={"method": "GET"},
            http_status=400,
            http_headers={},
            body='{"error": {"code": 100, "message": "Invalid parameter"}}',
        )

        with patch("app.services.meta_insights_service.Ad") as mock_ad_cls:
            mock_ad = MagicMock()
            mock_ad.get_insights.side_effect = mock_error
            mock_ad_cls.return_value = mock_ad

            service = MetaInsightsService()
            results = service.fetch_ad_insights("ad_invalid", "2025-01-15", "2025-01-15")
            assert results == []
