import pytest

API = "/api/v1/campaigns"


async def _create_and_generate(client) -> str:
    """Helper: create a campaign and generate proposals, return campaign_id."""
    resp = await client.post(f"{API}/", json={"user_prompt": "Test campaign for proposals"})
    campaign_id = resp.json()["id"]
    await client.post(f"{API}/{campaign_id}/generate")
    return campaign_id


@pytest.mark.asyncio
async def test_generate_proposals_creates_three(client):
    resp = await client.post(f"{API}/", json={"user_prompt": "Generate test"})
    campaign_id = resp.json()["id"]
    gen_resp = await client.post(f"{API}/{campaign_id}/generate")
    assert gen_resp.status_code == 200
    assert gen_resp.json()["status"] == "proposals_ready"

    props_resp = await client.get(f"{API}/{campaign_id}/proposals")
    assert props_resp.status_code == 200
    proposals = props_resp.json()
    assert len(proposals) == 3


@pytest.mark.asyncio
async def test_get_proposals(client):
    campaign_id = await _create_and_generate(client)
    resp = await client.get(f"{API}/{campaign_id}/proposals")
    assert resp.status_code == 200
    proposals = resp.json()
    assert len(proposals) == 3
    for p in proposals:
        assert "copy_text" in p
        assert "script" in p
        assert "image_prompt" in p
        assert "target_audience" in p


@pytest.mark.asyncio
async def test_select_proposal(client):
    campaign_id = await _create_and_generate(client)
    props = (await client.get(f"{API}/{campaign_id}/proposals")).json()
    proposal_id = props[0]["id"]

    resp = await client.post(f"{API}/{campaign_id}/select/{proposal_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "image_generating"
    assert data["selected_proposal_id"] == proposal_id


@pytest.mark.asyncio
async def test_select_proposal_unselects_others(client):
    campaign_id = await _create_and_generate(client)
    props = (await client.get(f"{API}/{campaign_id}/proposals")).json()

    # Select first
    await client.post(f"{API}/{campaign_id}/select/{props[0]['id']}")
    # Select second
    await client.post(f"{API}/{campaign_id}/select/{props[1]['id']}")

    # Check only second is selected
    updated_props = (await client.get(f"{API}/{campaign_id}/proposals")).json()
    for p in updated_props:
        if p["id"] == props[1]["id"]:
            assert p["is_selected"] is True
        else:
            assert p["is_selected"] is False


@pytest.mark.asyncio
async def test_update_proposal_marks_edited(client):
    campaign_id = await _create_and_generate(client)
    props = (await client.get(f"{API}/{campaign_id}/proposals")).json()
    proposal_id = props[0]["id"]

    resp = await client.put(
        f"{API}/{campaign_id}/proposals/{proposal_id}",
        json={"copy_text": "Edited text", "whatsapp_number": "+573001234567"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["copy_text"] == "Edited text"
    assert data["whatsapp_number"] == "+573001234567"
    assert data["is_edited"] is True


@pytest.mark.asyncio
async def test_generate_proposals_for_published_fails(client):
    campaign_id = await _create_and_generate(client)
    # Publish the campaign
    props = (await client.get(f"{API}/{campaign_id}/proposals")).json()
    await client.post(f"{API}/{campaign_id}/select/{props[0]['id']}")
    await client.post(f"{API}/{campaign_id}/publish")

    # Try to generate again — should fail
    resp = await client.post(f"{API}/{campaign_id}/generate")
    assert resp.status_code == 400
