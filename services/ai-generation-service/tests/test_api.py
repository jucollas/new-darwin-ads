import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.schemas.ai import GenerateProposalsResponse, MutateProposalResponse, ProposalResponse, TargetAudienceResponse


def _make_proposals_response() -> GenerateProposalsResponse:
    audience = TargetAudienceResponse(
        age_min=25, age_max=35, genders=["female"],
        interests=["fitness"], locations=["CO"],
    )
    proposal = ProposalResponse(
        copy_text="Test copy",
        script="Test script",
        image_prompt="Test image",
        target_audience=audience,
        cta_type="whatsapp_chat",
        whatsapp_number=None,
    )
    return GenerateProposalsResponse(
        proposals=[proposal, proposal, proposal],
        model_used="gpt-4o-mini",
        prompt_tokens=500,
        completion_tokens=1000,
    )


def _make_mutate_response() -> MutateProposalResponse:
    audience = TargetAudienceResponse(
        age_min=22, age_max=38, genders=["female"],
        interests=["fitness", "technology"], locations=["CO"],
    )
    return MutateProposalResponse(
        mutated_proposal=ProposalResponse(
            copy_text="Mutated copy",
            script="Mutated script",
            image_prompt="Mutated image",
            target_audience=audience,
            cta_type="whatsapp_chat",
            whatsapp_number=None,
        ),
        mutations_applied=["Changed copy angle"],
        model_used="gpt-4o-mini",
    )


@pytest.mark.asyncio
async def test_generate_proposals_endpoint_success():
    mock_result = _make_proposals_response()

    with patch("app.api.router.GPTService") as MockService:
        instance = MockService.return_value
        instance.generate_proposals = AsyncMock(return_value=mock_result)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/ai/generate/proposals",
                json={"user_prompt": "Vender zapatos deportivos"},
            )

    assert response.status_code == 200
    data = response.json()
    assert len(data["proposals"]) == 3
    assert data["model_used"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_generate_proposals_endpoint_empty_prompt():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/ai/generate/proposals",
            json={"user_prompt": "   "},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_generate_proposals_endpoint_ai_failure():
    with patch("app.api.router.GPTService") as MockService:
        instance = MockService.return_value
        instance.generate_proposals = AsyncMock(side_effect=RuntimeError("GPT failed"))

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/ai/generate/proposals",
                json={"user_prompt": "Test prompt"},
            )

    assert response.status_code == 502
    assert "GPT failed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_mutate_endpoint_success():
    mock_result = _make_mutate_response()

    with patch("app.api.router.GPTService") as MockService:
        instance = MockService.return_value
        instance.mutate_proposal = AsyncMock(return_value=mock_result)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/ai/generate/mutate",
                json={
                    "original_proposal": {
                        "copy_text": "Original",
                        "script": "Scene",
                        "image_prompt": "Photo",
                        "target_audience": {
                            "age_min": 25, "age_max": 35,
                            "genders": ["female"],
                            "interests": ["fitness"],
                            "locations": ["CO"],
                        },
                        "cta_type": "whatsapp_chat",
                        "whatsapp_number": None,
                    },
                    "mutation_rate": 0.3,
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert data["mutated_proposal"]["copy_text"] == "Mutated copy"
    assert len(data["mutations_applied"]) > 0


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "ai-generation-service"
