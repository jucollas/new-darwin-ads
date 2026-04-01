import pytest


@pytest.mark.asyncio
async def test_health(test_client):
    async with test_client as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["service"] == "image-generation-service"


@pytest.mark.asyncio
async def test_health_prefixed(test_client):
    async with test_client as client:
        response = await client.get("/api/v1/images/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
