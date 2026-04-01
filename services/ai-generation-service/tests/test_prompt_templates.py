from app.services.prompt_templates import (
    SYSTEM_PROMPT_PROPOSALS,
    SYSTEM_PROMPT_MUTATE,
    build_user_prompt_proposals,
    build_user_prompt_mutate,
)


def test_build_user_prompt_basic():
    result = build_user_prompt_proposals("Vender zapatos deportivos")
    assert "Campaign description: Vender zapatos deportivos" in result


def test_build_user_prompt_with_full_context():
    ctx = {
        "business_name": "ZapaFit",
        "industry": "fashion",
        "whatsapp_number": "+573001234567",
        "location": "Bogot\u00e1, Colombia",
        "extra_info": "Tienda online",
    }
    result = build_user_prompt_proposals("Vender zapatos", ctx)
    assert "Business name: ZapaFit" in result
    assert "Industry: fashion" in result
    assert "WhatsApp number: +573001234567" in result
    assert "Business location: Bogot\u00e1, Colombia" in result
    assert "Additional info: Tienda online" in result


def test_build_user_prompt_with_partial_context():
    ctx = {
        "business_name": "ZapaFit",
        "industry": None,
        "whatsapp_number": None,
        "location": "Bogot\u00e1",
        "extra_info": None,
    }
    result = build_user_prompt_proposals("Vender zapatos", ctx)
    assert "Business name: ZapaFit" in result
    assert "Business location: Bogot\u00e1" in result
    assert "Industry" not in result
    assert "WhatsApp number" not in result


def test_build_mutate_prompt():
    proposal = {
        "copy_text": "Test copy",
        "script": "Test script",
        "image_prompt": "Test image",
        "target_audience": {"age_min": 25, "age_max": 35},
        "cta_type": "whatsapp_chat",
    }
    result = build_user_prompt_mutate(proposal, 0.3, "Zapatos deportivos")
    assert "Mutation rate: 0.3" in result
    assert "Test copy" in result
    assert "Campaign context: Zapatos deportivos" in result


def test_system_prompts_not_empty():
    assert len(SYSTEM_PROMPT_PROPOSALS) > 100
    assert len(SYSTEM_PROMPT_MUTATE) > 100
    assert "JSON" in SYSTEM_PROMPT_PROPOSALS
    assert "JSON" in SYSTEM_PROMPT_MUTATE
