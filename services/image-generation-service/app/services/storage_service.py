import asyncio
import uuid

import structlog
from google.cloud import storage as gcs

from app.config import settings

logger = structlog.get_logger()

# Initialize GCS client lazily
_gcs_client = None


def _get_gcs_client():
    global _gcs_client
    if _gcs_client is None:
        _gcs_client = gcs.Client(project=settings.GOOGLE_CLOUD_PROJECT)
    return _gcs_client


class StorageError(Exception):
    """Raised when storage operations fail."""
    pass


async def upload_image(
    image_bytes: bytes,
    campaign_id: str,
    proposal_id: str,
    file_extension: str = "png",
) -> tuple[str, str]:
    """
    Upload image bytes to GCS.
    Returns (public_url, storage_path).

    File naming: campaigns/{campaign_id}/{proposal_id}/{uuid}.png
    """
    file_id = uuid.uuid4().hex[:12]
    storage_path = f"campaigns/{campaign_id}/{proposal_id}/{file_id}.{file_extension}"

    logger.info("storage_upload_start", path=storage_path, size_bytes=len(image_bytes))

    try:
        def _upload():
            client = _get_gcs_client()
            bucket = client.bucket(settings.GCS_BUCKET_NAME)
            blob = bucket.blob(storage_path)
            blob.upload_from_string(
                image_bytes,
                content_type=f"image/{file_extension}",
            )
            return blob.public_url

        public_url = await asyncio.to_thread(_upload)

        logger.info("storage_upload_success", path=storage_path, url=public_url)
        return public_url, storage_path

    except Exception as e:
        logger.exception("storage_upload_error", path=storage_path)
        raise StorageError(f"Failed to upload image: {str(e)}")


async def delete_image(storage_path: str) -> bool:
    """Delete an image from GCS by its storage path."""
    logger.info("storage_delete_start", path=storage_path)

    try:
        def _delete():
            client = _get_gcs_client()
            bucket = client.bucket(settings.GCS_BUCKET_NAME)
            blob = bucket.blob(storage_path)
            if blob.exists():
                blob.delete()
                return True
            return False

        deleted = await asyncio.to_thread(_delete)
        logger.info("storage_delete_result", path=storage_path, deleted=deleted)
        return deleted

    except Exception as e:
        logger.exception("storage_delete_error", path=storage_path)
        raise StorageError(f"Failed to delete image: {str(e)}")
