"""
Celery tasks for AI generation.

Dispatched by campaign-service when the user triggers proposal generation.
"""

import httpx
import structlog

from shared.celery_app.config import celery_app

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    name="tasks.ai_generate_proposals",
    queue="ai_tasks",
    max_retries=2,
    default_retry_delay=10,
    soft_time_limit=90,
    time_limit=120,
)
def ai_generate_proposals_task(
    self,
    campaign_id: str,
    user_prompt: str,
    business_context: dict | None = None,
):
    """
    1. Call GPT to generate 3 proposals
    2. Send proposals to campaign-service to store in DB
    3. Update campaign status to proposals_ready
    """
    try:
        logger.info("ai_task_started", campaign_id=campaign_id)

        with httpx.Client(timeout=90.0) as client:
            gen_response = client.post(
                "http://ai-generation-service:8002/api/v1/ai/generate/proposals",
                json={
                    "user_prompt": user_prompt,
                    "business_context": business_context or {},
                    "campaign_id": campaign_id,
                },
            )
            gen_response.raise_for_status()
            proposals_data = gen_response.json()["proposals"]

        with httpx.Client(timeout=30.0) as client:
            store_response = client.post(
                f"http://campaign-service:8001/api/v1/campaigns/internal/{campaign_id}/store-proposals",
                json={"proposals": proposals_data},
            )
            store_response.raise_for_status()

        logger.info("ai_task_completed", campaign_id=campaign_id, proposals_count=len(proposals_data))

    except Exception as exc:
        logger.error("ai_task_failed", campaign_id=campaign_id, error=str(exc))
        try:
            with httpx.Client(timeout=10.0) as client:
                client.put(
                    f"http://campaign-service:8001/api/v1/campaigns/internal/{campaign_id}/status",
                    json={"status": "failed"},
                )
        except Exception:
            pass
        self.retry(exc=exc)
