import httpx
import structlog

from shared.celery_app.config import celery_app

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    name="tasks.image_generate",
    queue="image_tasks",
    max_retries=2,
    default_retry_delay=15,
    time_limit=180,
    soft_time_limit=150,
)
def image_generate_task(
    self,
    campaign_id: str,
    proposal_id: str,
    image_prompt: str,
    aspect_ratio: str = "1:1",
):
    """
    Celery task that:
    1. Calls image-generation-service to generate + upload image
    2. Sends the image_url back to campaign-service to update the proposal
    3. Updates campaign status to 'image_ready'
    4. Dispatches notification (no-op for now)
    """
    try:
        logger.info(
            "image_task_start",
            campaign_id=campaign_id,
            proposal_id=proposal_id,
            prompt_length=len(image_prompt),
        )

        # Step 1: Call image service to generate and upload
        with httpx.Client(timeout=150.0) as client:
            response = client.post(
                "http://image-generation-service:8003/api/v1/images/generate",
                json={
                    "prompt": image_prompt,
                    "aspect_ratio": aspect_ratio,
                    "campaign_id": campaign_id,
                    "proposal_id": proposal_id,
                },
            )
            response.raise_for_status()
            result = response.json()

        image_url = result["image_url"]
        storage_path = result["storage_path"]

        logger.info(
            "image_task_generated",
            campaign_id=campaign_id,
            proposal_id=proposal_id,
            image_url=image_url,
        )

        # Step 2: Update proposal's image_url in campaign-service
        with httpx.Client(timeout=30.0) as client:
            update_response = client.put(
                f"http://campaign-service:8001/api/v1/campaigns/internal/{campaign_id}/proposals/{proposal_id}/image",
                json={
                    "image_url": image_url,
                    "storage_path": storage_path,
                },
            )
            update_response.raise_for_status()

        logger.info("image_task_proposal_updated", campaign_id=campaign_id, proposal_id=proposal_id)

        # Step 3: Update campaign status to 'image_ready'
        with httpx.Client(timeout=10.0) as client:
            client.put(
                f"http://campaign-service:8001/api/v1/campaigns/internal/{campaign_id}/status",
                json={"status": "image_ready"},
            )

        logger.info("image_task_complete", campaign_id=campaign_id)

        # Step 4: Dispatch notification (Phase 7 — no-op for now)
        try:
            celery_app.send_task(
                "tasks.notification_send",
                queue="notification_tasks",
                args=[campaign_id, "image_ready"],
            )
        except Exception:
            logger.warning("image_task_notification_failed", campaign_id=campaign_id)

    except httpx.HTTPStatusError as e:
        logger.error(
            "image_task_http_error",
            campaign_id=campaign_id,
            status=e.response.status_code,
            body=e.response.text[:500],
        )
        _set_campaign_failed(campaign_id)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
    except Exception as exc:
        logger.exception("image_task_unexpected_error", campaign_id=campaign_id)
        _set_campaign_failed(campaign_id)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)


def _set_campaign_failed(campaign_id: str):
    """Set campaign status to failed on unrecoverable error."""
    try:
        with httpx.Client(timeout=10.0) as client:
            client.put(
                f"http://campaign-service:8001/api/v1/campaigns/internal/{campaign_id}/status",
                json={"status": "failed"},
            )
    except Exception:
        logger.exception("image_task_fail_status_update_error", campaign_id=campaign_id)
