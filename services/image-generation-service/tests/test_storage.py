import pytest
from unittest.mock import patch, MagicMock

from app.services.storage_service import upload_image, delete_image


@pytest.mark.asyncio
async def test_upload_image():
    """Test image upload to GCS with mocked client."""
    mock_blob = MagicMock()
    mock_blob.public_url = "https://storage.googleapis.com/bucket/campaigns/c1/p1/abc.png"
    mock_blob.upload_from_string = MagicMock()

    mock_bucket = MagicMock()
    mock_bucket.blob = MagicMock(return_value=mock_blob)

    mock_client = MagicMock()
    mock_client.bucket = MagicMock(return_value=mock_bucket)

    with patch("app.services.storage_service._get_gcs_client", return_value=mock_client):
        url, path = await upload_image(b"fake-image-data", "campaign-1", "proposal-1")
        assert "storage.googleapis.com" in url
        assert "campaigns/campaign-1/proposal-1/" in path


@pytest.mark.asyncio
async def test_delete_image():
    """Test image deletion from GCS with mocked client."""
    mock_blob = MagicMock()
    mock_blob.exists = MagicMock(return_value=True)
    mock_blob.delete = MagicMock()

    mock_bucket = MagicMock()
    mock_bucket.blob = MagicMock(return_value=mock_blob)

    mock_client = MagicMock()
    mock_client.bucket = MagicMock(return_value=mock_bucket)

    with patch("app.services.storage_service._get_gcs_client", return_value=mock_client):
        deleted = await delete_image("campaigns/c1/p1/abc.png")
        assert deleted is True


@pytest.mark.asyncio
async def test_delete_image_not_found():
    """Test deletion of non-existent image."""
    mock_blob = MagicMock()
    mock_blob.exists = MagicMock(return_value=False)

    mock_bucket = MagicMock()
    mock_bucket.blob = MagicMock(return_value=mock_blob)

    mock_client = MagicMock()
    mock_client.bucket = MagicMock(return_value=mock_bucket)

    with patch("app.services.storage_service._get_gcs_client", return_value=mock_client):
        deleted = await delete_image("campaigns/nonexistent/path.png")
        assert deleted is False
