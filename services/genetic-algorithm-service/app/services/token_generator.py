"""
Generates internal service-to-service JWT tokens.

These tokens are signed with the SAME JWT_SECRET_KEY that all services
validate against. They contain a user_id and are short-lived (1 hour).
This allows the genetic-algorithm-service to authenticate with other
services when running via Celery Beat (where there is no incoming
request with a token to forward).
"""

import datetime

import jwt

from app.config import settings


def generate_service_token(user_id: str) -> str:
    """
    Generate a short-lived JWT for inter-service communication.

    Uses the same JWT_SECRET_KEY and JWT_ALGORITHM that all services
    validate against (from shared/auth/jwt_middleware.py).
    """
    now = datetime.datetime.utcnow()
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + datetime.timedelta(hours=1),
        "iss": settings.JWT_ISSUER,
        "service": "genetic-algorithm-service",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
