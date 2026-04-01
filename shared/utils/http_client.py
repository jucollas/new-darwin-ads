import httpx
from typing import Any

SERVICE_URLS = {
    "campaign": "http://campaign-service:8001",
    "ai": "http://ai-generation-service:8002",
    "image": "http://image-generation-service:8003",
    "publishing": "http://publishing-service:8004",
    "analytics": "http://analytics-service:8005",
    "genetic": "http://genetic-algorithm-service:8006",
    "notification": "http://notification-service:8007",
}


async def call_service(service: str, method: str, path: str, **kwargs) -> Any:
    url = f"{SERVICE_URLS[service]}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await getattr(client, method)(url, **kwargs)
        response.raise_for_status()
        return response.json()
