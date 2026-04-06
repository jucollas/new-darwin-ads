import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.meta_oauth_service import MetaOAuthService


class TestMetaOAuthService:

    def test_generate_login_url_contains_required_params(self):
        with patch("app.services.meta_oauth_service.settings") as mock_settings:
            mock_settings.META_APP_ID = "test_app_id"
            mock_settings.META_APP_SECRET = "test_secret"
            mock_settings.META_API_VERSION = "v25.0"
            mock_settings.META_GRAPH_API_BASE_URL = "https://graph.facebook.com"
            mock_settings.META_REDIRECT_URI = "http://localhost/callback"

            service = MetaOAuthService()
            url = service.generate_login_url(state="test_state_123")

            assert "https://www.facebook.com/v25.0/dialog/oauth" in url
            assert "client_id=test_app_id" in url
            assert "state=test_state_123" in url
            assert "ads_management" in url
            assert "ads_read" in url
            assert "business_management" in url
            assert "pages_manage_ads" in url
            assert "pages_read_engagement" in url
            assert "pages_show_list" in url
            assert "redirect_uri" in url

    @pytest.mark.asyncio
    async def test_exchange_code_for_token(self):
        with patch("app.services.meta_oauth_service.settings") as mock_settings:
            mock_settings.META_APP_ID = "test_app_id"
            mock_settings.META_APP_SECRET = "test_secret"
            mock_settings.META_API_VERSION = "v25.0"
            mock_settings.META_GRAPH_API_BASE_URL = "https://graph.facebook.com"
            mock_settings.META_REDIRECT_URI = "http://localhost/callback"

            service = MetaOAuthService()

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "access_token": "short_lived_token",
                "token_type": "bearer",
                "expires_in": 3600,
            }
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                result = await service.exchange_code_for_token("test_code")
                assert result["access_token"] == "short_lived_token"

    @pytest.mark.asyncio
    async def test_exchange_for_long_lived_token(self):
        with patch("app.services.meta_oauth_service.settings") as mock_settings:
            mock_settings.META_APP_ID = "test_app_id"
            mock_settings.META_APP_SECRET = "test_secret"
            mock_settings.META_API_VERSION = "v25.0"
            mock_settings.META_GRAPH_API_BASE_URL = "https://graph.facebook.com"
            mock_settings.META_REDIRECT_URI = "http://localhost/callback"

            service = MetaOAuthService()

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "access_token": "long_lived_token",
                "token_type": "bearer",
                "expires_in": 5184000,
            }
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                result = await service.exchange_for_long_lived_token("short_token")
                assert result["access_token"] == "long_lived_token"
                assert result["expires_in"] == 5184000

    @pytest.mark.asyncio
    async def test_fetch_user_ad_accounts(self):
        with patch("app.services.meta_oauth_service.settings") as mock_settings:
            mock_settings.META_APP_ID = "test_app_id"
            mock_settings.META_APP_SECRET = "test_secret"
            mock_settings.META_API_VERSION = "v25.0"
            mock_settings.META_GRAPH_API_BASE_URL = "https://graph.facebook.com"
            mock_settings.META_REDIRECT_URI = "http://localhost/callback"

            service = MetaOAuthService()

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": [
                    {"account_id": "123456", "name": "Test Account", "account_status": 1},
                ]
            }
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                accounts = await service.fetch_user_ad_accounts("test_token")
                assert len(accounts) == 1
                assert accounts[0]["account_id"] == "123456"
