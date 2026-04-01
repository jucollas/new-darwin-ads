import pytest

API = "/api/v1/campaigns"


@pytest.mark.asyncio
async def test_create_campaign(client):
    resp = await client.post(f"{API}/", json={"user_prompt": "Vender zapatos deportivos"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["user_prompt"] == "Vender zapatos deportivos"
    assert data["status"] == "draft"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_campaign_empty_prompt_fails(client):
    resp = await client.post(f"{API}/", json={"user_prompt": "   "})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_campaigns_empty(client):
    resp = await client.get(f"{API}/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_campaigns_with_data(client):
    await client.post(f"{API}/", json={"user_prompt": "Campaign 1"})
    await client.post(f"{API}/", json={"user_prompt": "Campaign 2"})
    resp = await client.get(f"{API}/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_campaigns_filtered_by_status(client):
    await client.post(f"{API}/", json={"user_prompt": "Draft campaign"})
    resp = await client.get(f"{API}/", params={"status": "published"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_campaign_detail(client):
    create_resp = await client.post(f"{API}/", json={"user_prompt": "Detail test"})
    campaign_id = create_resp.json()["id"]
    resp = await client.get(f"{API}/{campaign_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == campaign_id
    assert "proposals" in data


@pytest.mark.asyncio
async def test_get_campaign_not_found(client):
    resp = await client.get(f"{API}/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_campaign(client):
    create_resp = await client.post(f"{API}/", json={"user_prompt": "Original prompt"})
    campaign_id = create_resp.json()["id"]
    resp = await client.put(f"{API}/{campaign_id}", json={"user_prompt": "Updated prompt"})
    assert resp.status_code == 200
    assert resp.json()["user_prompt"] == "Updated prompt"


@pytest.mark.asyncio
async def test_delete_campaign_soft_delete(client):
    create_resp = await client.post(f"{API}/", json={"user_prompt": "To delete"})
    campaign_id = create_resp.json()["id"]
    resp = await client.delete(f"{API}/{campaign_id}")
    assert resp.status_code == 204

    # Should not appear in default list
    list_resp = await client.get(f"{API}/")
    ids = [c["id"] for c in list_resp.json()["items"]]
    assert campaign_id not in ids

    # Should appear when filtering by archived
    archived_resp = await client.get(f"{API}/", params={"status": "archived"})
    archived_ids = [c["id"] for c in archived_resp.json()["items"]]
    assert campaign_id in archived_ids
