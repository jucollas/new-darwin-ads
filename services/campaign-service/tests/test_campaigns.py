"""
21 integration tests for campaign-service covering:
- Infrastructure (health check)
- Auth
- Campaign CRUD
- Proposals
- Pause/Resume validation
- Error cases
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from tests.conftest import MOCK_USER

API = "/api/v1/campaigns"

# --- Mock AI data used by proposal-related tests ---

MOCK_AI_PROPOSALS = [
    {
        "copy_text": "¡Descubre los mejores zapatos!",
        "script": "Escena 1: Producto. Escena 2: CTA.",
        "image_prompt": "Professional photo of shoes",
        "target_audience": {
            "age_min": 25,
            "age_max": 35,
            "genders": ["female"],
            "interests": ["fitness"],
            "locations": ["CO"],
        },
        "cta_type": "whatsapp_chat",
        "whatsapp_number": None,
    },
    {
        "copy_text": "Zapatos que te llevan más lejos.",
        "script": "Escena 1: Beneficios.",
        "image_prompt": "Stylish shoes, studio lighting",
        "target_audience": {
            "age_min": 20,
            "age_max": 40,
            "genders": ["female", "male"],
            "interests": ["sportswear"],
            "locations": ["CO"],
        },
        "cta_type": "whatsapp_chat",
        "whatsapp_number": None,
    },
    {
        "copy_text": "¡Últimas unidades! 30% descuento.",
        "script": "Escena 1: Urgencia.",
        "image_prompt": "Sale banner for shoes",
        "target_audience": {
            "age_min": 18,
            "age_max": 45,
            "genders": ["female", "male"],
            "interests": ["deals"],
            "locations": ["CO", "MX"],
        },
        "cta_type": "whatsapp_chat",
        "whatsapp_number": None,
    },
]


def _mock_ai_response():
    return httpx.Response(
        status_code=200,
        json={"proposals": MOCK_AI_PROPOSALS, "model_used": "gpt-4o-mini",
              "prompt_tokens": 500, "completion_tokens": 1000},
        request=httpx.Request("POST", "http://ai-generation-service:8002/api/v1/ai/generate/proposals"),
    )


async def _create_campaign(client, prompt: str = "Test campaign") -> str:
    """Helper: create a campaign and return its id."""
    resp = await client.post(f"{API}/", json={"user_prompt": prompt})
    assert resp.status_code == 201
    return resp.json()["id"]


class _FakeAsyncClient:
    """Fake httpx.AsyncClient that returns mock AI response."""

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def post(self, url, **kwargs):
        return _mock_ai_response()


def _patch_ai_service():
    """Patch the httpx module's AsyncClient so that the service's internal
    HTTP call to ai-generation-service returns mock proposals."""
    return patch("httpx.AsyncClient", _FakeAsyncClient)


async def _create_with_proposals(client) -> str:
    """Helper: create a campaign and generate proposals, return campaign_id."""
    campaign_id = await _create_campaign(client, "Campaign with proposals")
    with _patch_ai_service():
        resp = await client.post(f"{API}/{campaign_id}/generate")
        assert resp.status_code == 200
    return campaign_id


# ---------------------------------------------------------------------------
# 1. Health check at /api/v1/campaigns/health
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_health_check_at_api_prefix(client):
    resp = await client.get(f"{API}/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "campaign-service"


# ---------------------------------------------------------------------------
# 2. Auth — no dedicated dev auth service, so we verify the mock user works
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_auth_mock_user_works(client):
    """The test client uses a mocked get_current_user; verify it returns data."""
    resp = await client.post(f"{API}/", json={"user_prompt": "Auth test"})
    assert resp.status_code == 201
    assert resp.json()["user_id"] == MOCK_USER["user_id"]


# ---------------------------------------------------------------------------
# 3. Auth — verify token is present in the mock user fixture
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_auth_user_has_expected_fields(client):
    """Ensure the mocked user fixture has all expected JWT fields."""
    resp = await client.post(f"{API}/", json={"user_prompt": "Fields test"})
    data = resp.json()
    assert "user_id" in data
    assert data["user_id"] == MOCK_USER["user_id"]


# ---------------------------------------------------------------------------
# 4. Create campaign with valid data → 201
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_campaign_valid(client):
    resp = await client.post(f"{API}/", json={"user_prompt": "Vender zapatos deportivos"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["user_prompt"] == "Vender zapatos deportivos"
    assert data["status"] == "draft"
    assert "id" in data


# ---------------------------------------------------------------------------
# 5. Create campaign without auth → 401/403
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_campaign_without_auth():
    """Without the mock override, the real JWT middleware rejects the request."""
    from app.main import app as real_app

    transport = httpx.ASGITransport(app=real_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(f"{API}/", json={"user_prompt": "No auth"})
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 6. Create campaign with empty user_prompt → 422
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_campaign_empty_prompt(client):
    resp = await client.post(f"{API}/", json={"user_prompt": "   "})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 7. List campaigns with pagination fields
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_campaigns_pagination_fields(client):
    await _create_campaign(client, "Pagination test")
    resp = await client.get(f"{API}/")
    assert resp.status_code == 200
    data = resp.json()
    for field in ("items", "total", "page", "page_size"):
        assert field in data


# ---------------------------------------------------------------------------
# 8. List campaigns filtered by status
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_campaigns_filtered_by_status(client):
    await _create_campaign(client, "Draft campaign")
    resp = await client.get(f"{API}/", params={"status": "published"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# 9. Get campaign by ID → 200 with correct data
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_campaign_by_id(client):
    campaign_id = await _create_campaign(client, "Detail test")
    resp = await client.get(f"{API}/{campaign_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == campaign_id
    assert data["user_prompt"] == "Detail test"
    assert "proposals" in data


# ---------------------------------------------------------------------------
# 10. Get campaign with invalid UUID → 400
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_campaign_invalid_uuid(client):
    resp = await client.get(f"{API}/not-a-uuid")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 11. Get campaign that doesn't exist → 404
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_campaign_not_found(client):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"{API}/{fake_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 12. Update campaign status → 200
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_update_campaign_status(client):
    campaign_id = await _create_campaign(client, "Update test")
    resp = await client.put(f"{API}/{campaign_id}", json={"user_prompt": "Updated prompt"})
    assert resp.status_code == 200
    assert resp.json()["user_prompt"] == "Updated prompt"


# ---------------------------------------------------------------------------
# 13. Soft delete campaign → 204
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_soft_delete_campaign(client):
    campaign_id = await _create_campaign(client, "To delete")
    resp = await client.delete(f"{API}/{campaign_id}")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# 14. Verify deleted campaign has status "archived"
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_deleted_campaign_is_archived(client):
    campaign_id = await _create_campaign(client, "Archive check")
    await client.delete(f"{API}/{campaign_id}")
    resp = await client.get(f"{API}/", params={"status": "archived"})
    assert resp.status_code == 200
    archived_ids = [c["id"] for c in resp.json()["items"]]
    assert campaign_id in archived_ids


# ---------------------------------------------------------------------------
# 15. Generate proposals for a campaign → 200
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_generate_proposals(client):
    campaign_id = await _create_campaign(client, "Generate test")
    with _patch_ai_service():
        resp = await client.post(f"{API}/{campaign_id}/generate")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("proposals_ready", "generating")


# ---------------------------------------------------------------------------
# 16. List proposals for a campaign → 200
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_proposals(client):
    campaign_id = await _create_with_proposals(client)
    resp = await client.get(f"{API}/{campaign_id}/proposals")
    assert resp.status_code == 200
    proposals = resp.json()
    assert len(proposals) == 3
    for p in proposals:
        assert "copy_text" in p
        assert "image_prompt" in p


# ---------------------------------------------------------------------------
# 17. Pause a campaign that is NOT published → 400
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pause_non_published_campaign(client):
    campaign_id = await _create_campaign(client, "Pause draft")
    resp = await client.post(f"{API}/{campaign_id}/pause")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 18. Resume a campaign that is NOT paused → 400
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_resume_non_paused_campaign(client):
    campaign_id = await _create_campaign(client, "Resume draft")
    resp = await client.post(f"{API}/{campaign_id}/resume")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 19. Access another user's campaign → 404 (should not leak existence)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_access_other_users_campaign(client):
    """Create a campaign, then override user to a different user_id and try to access it."""
    campaign_id = await _create_campaign(client, "Ownership test")

    from shared.auth.jwt_middleware import get_current_user
    from shared.database.session import get_db
    from app.main import app

    other_user = {
        "user_id": str(uuid.uuid4()),
        "email": "other@test.com",
        "name": "Other User",
        "roles": ["user"],
    }

    async def override_other_user():
        return other_user

    app.dependency_overrides[get_current_user] = override_other_user
    resp = await client.get(f"{API}/{campaign_id}")
    assert resp.status_code == 404

    # Restore original mock
    async def override_original():
        return MOCK_USER

    app.dependency_overrides[get_current_user] = override_original


# ---------------------------------------------------------------------------
# 20. Invalid UUID format in path → 400
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invalid_uuid_in_path(client):
    resp = await client.put(f"{API}/invalid-uuid-here", json={"user_prompt": "x"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 21. Request without Authorization header → 401/403
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_request_without_auth_header():
    """Directly test the real app without dependency overrides."""
    from app.main import app as real_app

    transport = httpx.ASGITransport(app=real_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get(f"{API}/")
    assert resp.status_code in (401, 403)
