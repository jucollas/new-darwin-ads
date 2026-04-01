import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_generate_image_success(test_client, mock_image_bytes):
    """Test image generation with mocked Vertex AI and GCS."""
    mock_pil = MagicMock()
    mock_pil.save = MagicMock(side_effect=lambda buf, **kw: buf.write(mock_image_bytes))

    mock_imagen_image = MagicMock()
    mock_imagen_image._pil_image = mock_pil

    mock_response = MagicMock()
    mock_response.images = [mock_imagen_image]

    mock_model = MagicMock()
    mock_model.generate_images = MagicMock(return_value=mock_response)

    with patch("app.services.imagen_service.ImageGenerationModel.from_pretrained", return_value=mock_model):
        with patch(
            "app.services.storage_service.upload_image",
            new_callable=AsyncMock,
            return_value=("https://storage.googleapis.com/bucket/test.png", "campaigns/test/test.png"),
        ):
            async with test_client as client:
                response = await client.post(
                    "/api/v1/images/generate",
                    json={
                        "prompt": "Professional product photo, athletic shoes",
                        "aspect_ratio": "1:1",
                        "campaign_id": "test-campaign-id",
                        "proposal_id": "test-proposal-id",
                    },
                )
                assert response.status_code == 200
                data = response.json()
                assert "image_url" in data
                assert "storage_path" in data
                assert data["image_url"].startswith("https://")


@pytest.mark.asyncio
async def test_generate_image_empty_prompt(test_client):
    """Test that empty prompt is rejected."""
    async with test_client as client:
        response = await client.post(
            "/api/v1/images/generate",
            json={"prompt": "  ", "aspect_ratio": "1:1", "campaign_id": "x", "proposal_id": "y"},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_generate_image_invalid_ratio(test_client):
    """Test that invalid aspect ratio is rejected."""
    async with test_client as client:
        response = await client.post(
            "/api/v1/images/generate",
            json={"prompt": "test", "aspect_ratio": "5:3", "campaign_id": "x", "proposal_id": "y"},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_generate_image_vertex_error(test_client):
    """Test handling when Vertex AI fails."""
    with patch("app.services.imagen_service.ImageGenerationModel.from_pretrained") as mock_model_cls:
        mock_model = MagicMock()
        mock_model.generate_images = MagicMock(side_effect=Exception("Vertex AI unavailable"))
        mock_model_cls.return_value = mock_model

        async with test_client as client:
            response = await client.post(
                "/api/v1/images/generate",
                json={"prompt": "test", "aspect_ratio": "1:1", "campaign_id": "x", "proposal_id": "y"},
            )
            assert response.status_code == 502
