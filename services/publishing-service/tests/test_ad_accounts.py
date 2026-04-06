import pytest
from unittest.mock import patch, AsyncMock


pytestmark = pytest.mark.asyncio


class TestAdAccountEndpoints:
    """Tests for ad account CRUD endpoints."""

    async def test_create_ad_account_success(self, client):
        response = await client.post(
            "/api/v1/publish/ad-accounts",
            json={
                "meta_ad_account_id": "act_123456789",
                "meta_page_id": "page_001",
                "access_token": "EAAtest_token_value",
                "meta_business_id": "biz_001",
                "whatsapp_phone_number": "+573001234567",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["meta_ad_account_id"] == "act_123456789"
        assert data["meta_page_id"] == "page_001"
        assert data["is_active"] is True
        # access_token should NOT be in response
        assert "access_token" not in data
        assert "access_token_encrypted" not in data

    async def test_create_ad_account_invalid_act_prefix(self, client):
        response = await client.post(
            "/api/v1/publish/ad-accounts",
            json={
                "meta_ad_account_id": "123456789",
                "meta_page_id": "page_001",
                "access_token": "EAAtest_token_value",
            },
        )
        assert response.status_code == 422

    async def test_create_ad_account_empty_token(self, client):
        response = await client.post(
            "/api/v1/publish/ad-accounts",
            json={
                "meta_ad_account_id": "act_123456789",
                "meta_page_id": "page_001",
                "access_token": "  ",
            },
        )
        assert response.status_code == 422

    async def test_create_ad_account_invalid_phone(self, client):
        response = await client.post(
            "/api/v1/publish/ad-accounts",
            json={
                "meta_ad_account_id": "act_123456789",
                "meta_page_id": "page_001",
                "access_token": "EAAtoken",
                "whatsapp_phone_number": "12345",
            },
        )
        assert response.status_code == 422

    async def test_list_ad_accounts_empty(self, client):
        response = await client.get("/api/v1/publish/ad-accounts")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_ad_accounts_with_data(self, client):
        # Create an account first
        await client.post(
            "/api/v1/publish/ad-accounts",
            json={
                "meta_ad_account_id": "act_111",
                "meta_page_id": "page_001",
                "access_token": "EAAtoken1",
            },
        )
        response = await client.get("/api/v1/publish/ad-accounts")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 1

    async def test_delete_ad_account_success(self, client):
        # Create
        create_resp = await client.post(
            "/api/v1/publish/ad-accounts",
            json={
                "meta_ad_account_id": "act_del_test",
                "meta_page_id": "page_001",
                "access_token": "EAAtoken_delete",
            },
        )
        account_id = create_resp.json()["id"]

        # Delete
        delete_resp = await client.delete(f"/api/v1/publish/ad-accounts/{account_id}")
        assert delete_resp.status_code == 204

        # Verify it's not listed anymore (is_active=False)
        list_resp = await client.get("/api/v1/publish/ad-accounts")
        ids = [a["id"] for a in list_resp.json()["items"]]
        assert account_id not in ids

    async def test_delete_ad_account_not_found(self, client):
        response = await client.delete(
            "/api/v1/publish/ad-accounts/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404

    async def test_verify_ad_account_not_found(self, client):
        response = await client.get(
            "/api/v1/publish/ad-accounts/00000000-0000-0000-0000-000000000000/verify"
        )
        assert response.status_code == 404

    async def test_set_whatsapp_number_success(self, client):
        # Create account
        create_resp = await client.post(
            "/api/v1/publish/ad-accounts",
            json={
                "meta_ad_account_id": "act_whatsapp_test",
                "meta_page_id": "page_001",
                "access_token": "EAAtoken_wa",
            },
        )
        account_id = create_resp.json()["id"]

        # Set WhatsApp number
        resp = await client.put(
            f"/api/v1/publish/ad-accounts/{account_id}/whatsapp",
            json={"whatsapp_number": "+573001234567"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["whatsapp_phone_number"] == "+573001234567"

    async def test_set_whatsapp_number_rejects_invalid(self, client):
        create_resp = await client.post(
            "/api/v1/publish/ad-accounts",
            json={
                "meta_ad_account_id": "act_whatsapp_invalid",
                "meta_page_id": "page_001",
                "access_token": "EAAtoken_wa2",
            },
        )
        account_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/publish/ad-accounts/{account_id}/whatsapp",
            json={"whatsapp_number": "12345"},
        )
        assert resp.status_code == 422

    async def test_set_whatsapp_number_not_found(self, client):
        resp = await client.put(
            "/api/v1/publish/ad-accounts/00000000-0000-0000-0000-000000000000/whatsapp",
            json={"whatsapp_number": "+573001234567"},
        )
        assert resp.status_code == 404


class TestWhatsAppNumberValidation:
    """Bug #2: Verify E.164 validation on the SetWhatsAppNumberRequest schema."""

    def test_valid_colombian_number(self):
        from app.schemas.publishing import SetWhatsAppNumberRequest
        req = SetWhatsAppNumberRequest(whatsapp_number="+573001234567")
        assert req.whatsapp_number == "+573001234567"

    def test_valid_us_number(self):
        from app.schemas.publishing import SetWhatsAppNumberRequest
        req = SetWhatsAppNumberRequest(whatsapp_number="+14155551234")
        assert req.whatsapp_number == "+14155551234"

    def test_rejects_number_without_plus(self):
        from app.schemas.publishing import SetWhatsAppNumberRequest
        with pytest.raises(ValueError, match="E.164"):
            SetWhatsAppNumberRequest(whatsapp_number="573001234567")

    def test_rejects_too_short(self):
        from app.schemas.publishing import SetWhatsAppNumberRequest
        with pytest.raises(ValueError, match="E.164"):
            SetWhatsAppNumberRequest(whatsapp_number="+123")

    def test_rejects_empty_string(self):
        from app.schemas.publishing import SetWhatsAppNumberRequest
        with pytest.raises(ValueError, match="E.164"):
            SetWhatsAppNumberRequest(whatsapp_number="")

    def test_strips_whitespace(self):
        from app.schemas.publishing import SetWhatsAppNumberRequest
        req = SetWhatsAppNumberRequest(whatsapp_number="  +573001234567  ")
        assert req.whatsapp_number == "+573001234567"
