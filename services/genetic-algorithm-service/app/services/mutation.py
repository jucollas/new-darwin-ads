import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


class MutationService:
    """
    Dispatches mutation requests to ai-generation-service and handles responses.
    """

    async def mutate_proposal(
        self,
        original_proposal: dict,
        mutate_field: str,
        mutation_rate: float,
    ) -> dict:
        """
        POST to ai-generation-service /api/v1/ai/generate/mutate.
        Retries up to 2 times with 5s delay. Returns original on failure.
        """
        payload = {
            "original_proposal": {
                "copy_text": original_proposal.get("copy_text", ""),
                "script": original_proposal.get("script", ""),
                "image_prompt": original_proposal.get("image_prompt", ""),
                "target_audience": original_proposal.get("target_audience", {}),
                "cta_type": original_proposal.get("cta_type", "whatsapp_chat"),
            },
            "mutate_field": mutate_field,
            "mutation_rate": mutation_rate,
            "context": {
                "market": "Colombia",
                "platform": "WhatsApp",
                "objective": "OUTCOME_ENGAGEMENT",
            },
        }

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{settings.AI_SERVICE_URL}/api/v1/ai/generate/mutate",
                        json=payload,
                    )
                    resp.raise_for_status()
                    result = resp.json()
                    logger.info(
                        "mutation_success",
                        mutate_field=mutate_field,
                        attempt=attempt + 1,
                    )
                    return result
            except Exception as exc:
                logger.warning(
                    "mutation_attempt_failed",
                    mutate_field=mutate_field,
                    attempt=attempt + 1,
                    error=str(exc),
                )
                if attempt < max_retries:
                    import asyncio
                    await asyncio.sleep(5)

        logger.error(
            "mutation_all_retries_failed",
            mutate_field=mutate_field,
        )
        return original_proposal
