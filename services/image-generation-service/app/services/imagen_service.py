import asyncio
import io

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable
import vertexai
from vertexai.preview.vision_models import ImageGenerationModel

from app.config import settings

logger = structlog.get_logger()

# Initialize Vertex AI on module load
vertexai.init(
    project=settings.GOOGLE_CLOUD_PROJECT,
    location=settings.GOOGLE_CLOUD_LOCATION,
)


class ImageGenerationError(Exception):
    """Raised when image generation fails."""
    pass


# Map aspect ratio strings to Imagen 3 accepted values
ASPECT_RATIO_MAP = {
    "1:1": "1:1",
    "9:16": "9:16",
    "16:9": "16:9",
    "4:3": "4:3",
    "3:4": "3:4",
}

# Safety/quality prefix appended to every prompt to improve ad image quality
PROMPT_ENHANCEMENT = (
    "Professional advertising photography, high resolution, studio quality lighting, "
    "clean composition, no text overlays, no watermarks, no logos, "
    "commercially viable, brand-safe content. "
)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=3, max=30),
    retry=retry_if_exception_type((ResourceExhausted, ServiceUnavailable)),
    before_sleep=lambda rs: logger.warning("imagen_retry", attempt=rs.attempt_number),
)
async def generate_image(prompt: str, aspect_ratio: str = "1:1") -> bytes:
    """
    Generate an image using Google Imagen 3.
    Returns raw PNG image bytes.
    Raises ImageGenerationError on failure.
    """
    resolved_ratio = ASPECT_RATIO_MAP.get(aspect_ratio, "1:1")
    enhanced_prompt = PROMPT_ENHANCEMENT + prompt

    logger.info("imagen_generate_start", prompt_length=len(enhanced_prompt), aspect_ratio=resolved_ratio)

    try:
        model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-002")

        response = await asyncio.to_thread(
            lambda: model.generate_images(
                prompt=enhanced_prompt,
                number_of_images=1,
                aspect_ratio=resolved_ratio,
                safety_filter_level="block_few",
                person_generation="allow_adult",
            ),
        )

        if not response.images:
            raise ImageGenerationError("Imagen 3 returned no images")

        image = response.images[0]

        # Convert to bytes
        img_bytes_io = io.BytesIO()
        image._pil_image.save(img_bytes_io, format="PNG", optimize=True)
        img_bytes = img_bytes_io.getvalue()

        logger.info("imagen_generate_success", size_bytes=len(img_bytes))
        return img_bytes

    except (ResourceExhausted, ServiceUnavailable):
        raise  # Let tenacity retry these
    except ImageGenerationError:
        raise
    except Exception as e:
        logger.exception("imagen_generate_error", error=str(e))
        raise ImageGenerationError(f"Image generation failed: {str(e)}")
