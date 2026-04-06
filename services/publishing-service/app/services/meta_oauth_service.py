import urllib.parse

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()

OAUTH_SCOPES = "ads_management,ads_read,business_management,pages_manage_ads,pages_read_engagement,pages_show_list,whatsapp_business_management,whatsapp_business_messaging"


class MetaOAuthService:
    """Handles the Meta OAuth 2.0 flow.

    Uses httpx for OAuth token exchange — the facebook-business SDK does not
    cover OAuth endpoints.
    """

    def __init__(self):
        self.app_id = settings.META_APP_ID
        self.app_secret = settings.META_APP_SECRET
        self.api_version = settings.META_API_VERSION
        self.graph_base = settings.META_GRAPH_API_BASE_URL
        self.redirect_uri = settings.META_REDIRECT_URI

    def generate_login_url(self, state: str) -> str:
        """Build the Facebook OAuth dialog URL."""
        params = urllib.parse.urlencode({
            "client_id": self.app_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": OAUTH_SCOPES,
            "response_type": "code",
        })
        return f"https://www.facebook.com/{self.api_version}/dialog/oauth?{params}"

    async def exchange_code_for_token(self, code: str) -> dict:
        """Exchange authorization code for short-lived access token."""
        url = f"{self.graph_base}/{self.api_version}/oauth/access_token"
        params = {
            "client_id": self.app_id,
            "redirect_uri": self.redirect_uri,
            "client_secret": self.app_secret,
            "code": code,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def exchange_for_long_lived_token(self, short_lived_token: str) -> dict:
        """Exchange short-lived token for long-lived token (~60 days)."""
        url = f"{self.graph_base}/{self.api_version}/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self.app_id,
            "client_secret": self.app_secret,
            "fb_exchange_token": short_lived_token,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def fetch_user_ad_accounts(self, access_token: str) -> list[dict]:
        """Fetch the authenticated user's ad accounts."""
        url = f"{self.graph_base}/{self.api_version}/me/adaccounts"
        params = {
            "fields": "account_id,name,account_status,business",
            "access_token": access_token,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json().get("data", [])

    async def fetch_user_pages(self, access_token: str) -> list[dict]:
        """Fetch the authenticated user's pages."""
        url = f"{self.graph_base}/{self.api_version}/me/accounts"
        params = {
            "fields": "id,name,access_token",
            "access_token": access_token,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json().get("data", [])
