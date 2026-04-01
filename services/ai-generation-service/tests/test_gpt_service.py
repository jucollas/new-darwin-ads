import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.gpt_service import GPTService


def _make_openai_response(content: dict, prompt_tokens: int = 500, completion_tokens: int = 1000):
    """Create a mock OpenAI ChatCompletion response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(content)
    mock_response.usage.prompt_tokens = prompt_tokens
    mock_response.usage.completion_tokens = completion_tokens
    mock_response.usage.total_tokens = prompt_tokens + completion_tokens
    return mock_response


@pytest.mark.asyncio
async def test_generate_proposals_success(mock_openai_proposals_response):
    service = GPTService()
    mock_resp = _make_openai_response(mock_openai_proposals_response)

    with patch.object(service.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_resp):
        result = await service.generate_proposals("Vender zapatos deportivos")

    assert len(result.proposals) == 3
    assert result.model_used == service.model
    assert result.prompt_tokens == 500
    assert result.completion_tokens == 1000
    assert result.proposals[0].cta_type == "whatsapp_chat"


@pytest.mark.asyncio
async def test_generate_proposals_retries_on_parse_error(mock_openai_proposals_response):
    service = GPTService()
    bad_resp = MagicMock()
    bad_resp.choices = [MagicMock()]
    bad_resp.choices[0].message.content = "not valid json"

    good_resp = _make_openai_response(mock_openai_proposals_response)

    mock_create = AsyncMock(side_effect=[bad_resp, good_resp])
    with patch.object(service.client.chat.completions, "create", mock_create):
        result = await service.generate_proposals("Test prompt")

    assert len(result.proposals) == 3
    assert mock_create.call_count == 2


@pytest.mark.asyncio
async def test_generate_proposals_retries_on_rate_limit(mock_openai_proposals_response):
    from openai import RateLimitError
    import httpx

    service = GPTService()
    good_resp = _make_openai_response(mock_openai_proposals_response)

    mock_response = httpx.Response(status_code=429, request=httpx.Request("POST", "https://api.openai.com"))
    rate_err = RateLimitError("rate limited", response=mock_response, body=None)

    mock_create = AsyncMock(side_effect=[rate_err, good_resp])
    with patch.object(service.client.chat.completions, "create", mock_create):
        result = await service.generate_proposals("Test prompt")

    assert len(result.proposals) == 3
    assert mock_create.call_count == 2


@pytest.mark.asyncio
async def test_generate_proposals_fails_after_max_retries():
    service = GPTService()
    bad_resp = MagicMock()
    bad_resp.choices = [MagicMock()]
    bad_resp.choices[0].message.content = "bad json"

    mock_create = AsyncMock(return_value=bad_resp)
    with patch.object(service.client.chat.completions, "create", mock_create):
        with pytest.raises(RuntimeError, match="Failed to generate proposals after 3 attempts"):
            await service.generate_proposals("Test")

    assert mock_create.call_count == 3


@pytest.mark.asyncio
async def test_generate_proposals_fewer_than_3_pads_results():
    service = GPTService()
    content = {
        "proposals": [
            {
                "copy_text": "Solo una propuesta",
                "script": "Escena 1",
                "image_prompt": "photo",
                "target_audience": {"age_min": 20, "age_max": 30, "genders": ["female"], "interests": ["test"], "locations": ["CO"]},
                "cta_type": "whatsapp_chat",
                "whatsapp_number": None,
            },
            {
                "copy_text": "Segunda propuesta",
                "script": "Escena 1",
                "image_prompt": "photo",
                "target_audience": {"age_min": 20, "age_max": 30, "genders": ["male"], "interests": ["test"], "locations": ["CO"]},
                "cta_type": "whatsapp_chat",
                "whatsapp_number": None,
            },
        ]
    }
    mock_resp = _make_openai_response(content)

    with patch.object(service.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_resp):
        result = await service.generate_proposals("Test")

    assert len(result.proposals) == 3


@pytest.mark.asyncio
async def test_generate_proposals_truncates_long_copy():
    service = GPTService()
    long_copy = "A" * 600
    content = {
        "proposals": [
            {
                "copy_text": long_copy,
                "script": "Escena 1",
                "image_prompt": "photo",
                "target_audience": {"age_min": 20, "age_max": 30, "genders": ["female"], "interests": ["test"], "locations": ["CO"]},
                "cta_type": "whatsapp_chat",
            },
            {
                "copy_text": "Copy 2",
                "script": "Escena 1",
                "image_prompt": "photo",
                "target_audience": {"age_min": 20, "age_max": 30, "genders": ["female"], "interests": ["test"], "locations": ["CO"]},
                "cta_type": "whatsapp_chat",
            },
            {
                "copy_text": "Copy 3",
                "script": "Escena 1",
                "image_prompt": "photo",
                "target_audience": {"age_min": 20, "age_max": 30, "genders": ["female"], "interests": ["test"], "locations": ["CO"]},
                "cta_type": "whatsapp_chat",
            },
        ]
    }
    mock_resp = _make_openai_response(content)

    with patch.object(service.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_resp):
        result = await service.generate_proposals("Test")

    assert len(result.proposals[0].copy_text) <= 500


@pytest.mark.asyncio
async def test_mutate_proposal_success(mock_openai_mutate_response):
    service = GPTService()
    mock_resp = _make_openai_response(mock_openai_mutate_response)

    original = {
        "copy_text": "Original copy",
        "script": "Original script",
        "image_prompt": "Original image",
        "target_audience": {"age_min": 25, "age_max": 35, "genders": ["female"], "interests": ["fitness"], "locations": ["CO"]},
        "cta_type": "whatsapp_chat",
        "whatsapp_number": None,
    }

    with patch.object(service.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_resp):
        result = await service.mutate_proposal(original, mutation_rate=0.3)

    assert result.mutated_proposal.copy_text != ""
    assert len(result.mutations_applied) > 0
    assert result.model_used == service.model


@pytest.mark.asyncio
async def test_mutate_proposal_higher_rate_increases_temperature():
    service = GPTService()
    content = {
        "mutated_proposal": {
            "copy_text": "Mutated",
            "script": "Scene",
            "image_prompt": "Photo",
            "target_audience": {"age_min": 20, "age_max": 30, "genders": ["female"], "interests": ["test"], "locations": ["CO"]},
            "cta_type": "whatsapp_chat",
            "whatsapp_number": None,
        },
        "mutations_applied": ["Changed everything"],
    }
    mock_resp = _make_openai_response(content)
    mock_create = AsyncMock(return_value=mock_resp)

    with patch.object(service.client.chat.completions, "create", mock_create):
        await service.mutate_proposal({"copy_text": "test"}, mutation_rate=0.5)

    call_kwargs = mock_create.call_args[1]
    expected_temp = min(service.__class.__init__.__code__.co_consts[0] if False else 0.8 + 0.5, 1.5)
    assert call_kwargs["temperature"] == pytest.approx(1.3, abs=0.1)
