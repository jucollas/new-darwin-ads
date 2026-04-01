"""
Tests for the AI integration in campaign-service.

These tests mock the external HTTP call to ai-generation-service.
They test the campaign-service endpoints and service methods that interact with AI.
"""

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import httpx


MOCK_AI_PROPOSALS = [
    {
        "copy_text": "\u00a1Descubre los mejores zapatos! Escr\u00edbenos por WhatsApp.",
        "script": "Escena 1: Producto. Escena 2: CTA WhatsApp.",
        "image_prompt": "Professional photo of shoes, white background",
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
        "copy_text": "Zapatos que te llevan m\u00e1s lejos. \u00a1Ch\u00e1tea con nosotros!",
        "script": "Escena 1: Beneficios. Escena 2: CTA.",
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
        "copy_text": "\u00a1\u00daltimas unidades! 30% descuento. Escr\u00edbenos ya.",
        "script": "Escena 1: Urgencia. Escena 2: Descuento. Escena 3: CTA.",
        "image_prompt": "Sale banner for shoes, urgency design",
        "target_audience": {
            "age_min": 18,
            "age_max": 45,
            "genders": ["female", "male"],
            "interests": ["deals", "shopping"],
            "locations": ["CO", "MX"],
        },
        "cta_type": "whatsapp_chat",
        "whatsapp_number": None,
    },
]


def _mock_ai_response():
    """Create a mock httpx.Response for ai-generation-service."""
    return httpx.Response(
        status_code=200,
        json={
            "proposals": MOCK_AI_PROPOSALS,
            "model_used": "gpt-4o-mini",
            "prompt_tokens": 500,
            "completion_tokens": 1000,
        },
        request=httpx.Request("POST", "http://ai-generation-service:8002/api/v1/ai/generate/proposals"),
    )


@pytest.mark.asyncio
async def test_generate_endpoint_changes_status(client):
    """After calling generate, campaign status should transition properly."""
    # Create campaign
    resp = await client.post("/api/v1/campaigns/", json={"user_prompt": "Vender zapatos deportivos"})
    assert resp.status_code == 201
    campaign_id = resp.json()["id"]

    # Mock the AI service call
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=_mock_ai_response()):
        resp = await client.post(f"/api/v1/campaigns/{campaign_id}/generate")

    assert resp.status_code == 200
    data = resp.json()
    # In sync mode, status goes directly to proposals_ready
    assert data["status"] in ("proposals_ready", "generating")


@pytest.mark.asyncio
async def test_generate_endpoint_only_from_valid_statuses(client):
    """Cannot generate proposals from statuses like 'published'."""
    # Create and generate first
    resp = await client.post("/api/v1/campaigns/", json={"user_prompt": "Test campaign"})
    campaign_id = resp.json()["id"]

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=_mock_ai_response()):
        await client.post(f"/api/v1/campaigns/{campaign_id}/generate")

    # Get proposals and select one
    props_resp = await client.get(f"/api/v1/campaigns/{campaign_id}/proposals")
    proposal_id = props_resp.json()[0]["id"]

    # Mock celery to avoid dispatching real task
    with patch("shared.celery_app.config.celery_app.send_task"):
        await client.post(f"/api/v1/campaigns/{campaign_id}/select/{proposal_id}")

    # Publish
    await client.post(f"/api/v1/campaigns/{campaign_id}/publish")

    # Now try to generate from published — should fail
    resp = await client.post(f"/api/v1/campaigns/{campaign_id}/generate")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_generate_stores_real_proposals(client):
    """After sync generation, proposals should be stored in DB."""
    resp = await client.post("/api/v1/campaigns/", json={"user_prompt": "Restaurante de sushi en Bogot\u00e1"})
    campaign_id = resp.json()["id"]

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=_mock_ai_response()):
        await client.post(f"/api/v1/campaigns/{campaign_id}/generate")

    # Fetch proposals
    props_resp = await client.get(f"/api/v1/campaigns/{campaign_id}/proposals")
    assert props_resp.status_code == 200
    proposals = props_resp.json()
    assert len(proposals) == 3
    assert proposals[0]["cta_type"] == "whatsapp_chat"


@pytest.mark.asyncio
async def test_regenerate_replaces_old_proposals(client):
    """Regenerating should delete old proposals and create new ones."""
    resp = await client.post("/api/v1/campaigns/", json={"user_prompt": "Test regeneration"})
    campaign_id = resp.json()["id"]

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=_mock_ai_response()):
        await client.post(f"/api/v1/campaigns/{campaign_id}/generate")

    # Get first batch IDs
    props1 = await client.get(f"/api/v1/campaigns/{campaign_id}/proposals")
    ids1 = {p["id"] for p in props1.json()}

    # Regenerate
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=_mock_ai_response()):
        await client.post(f"/api/v1/campaigns/{campaign_id}/generate")

    # Get second batch IDs
    props2 = await client.get(f"/api/v1/campaigns/{campaign_id}/proposals")
    ids2 = {p["id"] for p in props2.json()}

    # IDs should be different (new proposals)
    assert len(props2.json()) == 3
    assert ids1 != ids2


@pytest.mark.asyncio
async def test_internal_store_proposals_endpoint(client):
    """Internal endpoint should store proposals correctly."""
    resp = await client.post("/api/v1/campaigns/", json={"user_prompt": "Internal test"})
    campaign_id = resp.json()["id"]

    # Call internal endpoint directly
    store_resp = await client.post(
        f"/api/v1/campaigns/internal/{campaign_id}/store-proposals",
        json={"proposals": MOCK_AI_PROPOSALS},
    )
    assert store_resp.status_code == 200
    assert store_resp.json()["proposals_stored"] == 3

    # Verify proposals are stored
    props_resp = await client.get(f"/api/v1/campaigns/{campaign_id}/proposals")
    assert len(props_resp.json()) == 3


@pytest.mark.asyncio
async def test_internal_status_update_endpoint(client):
    """Internal endpoint should update campaign status."""
    resp = await client.post("/api/v1/campaigns/", json={"user_prompt": "Status test"})
    campaign_id = resp.json()["id"]

    # Update status via internal endpoint
    status_resp = await client.put(
        f"/api/v1/campaigns/internal/{campaign_id}/status",
        json={"status": "generating"},
    )
    assert status_resp.status_code == 200

    # Verify status changed
    detail_resp = await client.get(f"/api/v1/campaigns/{campaign_id}")
    assert detail_resp.json()["status"] == "generating"


@pytest.mark.asyncio
async def test_internal_update_proposal_image(client):
    """Internal endpoint should update proposal image_url."""
    # Create campaign and proposals
    resp = await client.post("/api/v1/campaigns/", json={"user_prompt": "Image test"})
    campaign_id = resp.json()["id"]

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=_mock_ai_response()):
        await client.post(f"/api/v1/campaigns/{campaign_id}/generate")

    props_resp = await client.get(f"/api/v1/campaigns/{campaign_id}/proposals")
    proposal_id = props_resp.json()[0]["id"]

    # Update proposal image via internal endpoint
    image_resp = await client.put(
        f"/api/v1/campaigns/internal/{campaign_id}/proposals/{proposal_id}/image",
        json={
            "image_url": "https://storage.googleapis.com/bucket/test.png",
            "storage_path": "campaigns/test/test.png",
        },
    )
    assert image_resp.status_code == 200
    assert image_resp.json()["status"] == "ok"

    # Verify image_url is set
    props_resp = await client.get(f"/api/v1/campaigns/{campaign_id}/proposals")
    updated = next(p for p in props_resp.json() if p["id"] == proposal_id)
    assert updated["image_url"] == "https://storage.googleapis.com/bucket/test.png"


@pytest.mark.asyncio
async def test_select_proposal_dispatches_image_task(client):
    """Selecting a proposal should dispatch an image generation Celery task."""
    # Create campaign and proposals
    resp = await client.post("/api/v1/campaigns/", json={"user_prompt": "Select test"})
    campaign_id = resp.json()["id"]

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=_mock_ai_response()):
        await client.post(f"/api/v1/campaigns/{campaign_id}/generate")

    props_resp = await client.get(f"/api/v1/campaigns/{campaign_id}/proposals")
    proposal_id = props_resp.json()[0]["id"]

    # Mock celery send_task
    with patch("shared.celery_app.config.celery_app.send_task") as mock_send:
        resp = await client.post(f"/api/v1/campaigns/{campaign_id}/select/{proposal_id}")

    assert resp.status_code == 200
    assert resp.json()["status"] == "image_generating"

    # Verify Celery task was dispatched
    mock_send.assert_called_once_with(
        "tasks.image_generate",
        queue="image_tasks",
        args=[campaign_id, proposal_id, MOCK_AI_PROPOSALS[0]["image_prompt"], "1:1"],
    )
