from fastapi import APIRouter, HTTPException, status
import structlog

from app.schemas.image import (
    GenerateImageRequest,
    GenerateImageResponse,
    DeleteImageResponse,
)
from app.services.imagen_service import generate_image, ImageGenerationError
from app.services.storage_service import upload_image, delete_image, StorageError

logger = structlog.get_logger()
router = APIRouter(tags=["image-generation"])


@router.post("/generate", response_model=GenerateImageResponse)
async def generate(data: GenerateImageRequest):
    """Generate an advertising image and upload to GCS."""
    try:
        image_bytes = await generate_image(
            prompt=data.prompt,
            aspect_ratio=data.aspect_ratio,
        )

        public_url, storage_path = await upload_image(
            image_bytes=image_bytes,
            campaign_id=data.campaign_id,
            proposal_id=data.proposal_id,
        )

        return GenerateImageResponse(
            image_url=public_url,
            storage_path=storage_path,
            campaign_id=data.campaign_id,
            proposal_id=data.proposal_id,
        )

    except ImageGenerationError as e:
        logger.error("generate_endpoint_imagen_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Image generation failed: {str(e)}",
        )
    except StorageError as e:
        logger.error("generate_endpoint_storage_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Image storage failed: {str(e)}",
        )
    except Exception:
        logger.exception("generate_endpoint_unexpected_error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during image generation",
        )


@router.delete("/{storage_path:path}", response_model=DeleteImageResponse)
async def delete(storage_path: str):
    """Delete an image from GCS."""
    try:
        deleted = await delete_image(storage_path)
        return DeleteImageResponse(deleted=deleted, storage_path=storage_path)
    except StorageError as e:
        raise HTTPException(status_code=500, detail=str(e))
