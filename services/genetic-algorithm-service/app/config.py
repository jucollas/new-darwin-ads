from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    SERVICE_NAME: str = "genetic-algorithm-service"
    API_PREFIX: str = "/api/v1/optimize"
    ROOT_PATH: str = ""
    DATABASE_URL: str = "postgresql+asyncpg://adgen:changeme_in_production@postgres:5432/adgen_ai"
    REDIS_URL: str = "redis://redis:6379/0"
    JWT_SECRET_KEY: str = "changeme"
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "adgen-ai"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Inter-service URLs
    CAMPAIGN_SERVICE_URL: str = "http://campaign-service:8001"
    ANALYTICS_SERVICE_URL: str = "http://analytics-service:8005"
    PUBLISHING_SERVICE_URL: str = "http://publishing-service:8004"
    AI_SERVICE_URL: str = "http://ai-generation-service:8002"

    # Optimization schedule
    OPTIMIZATION_INTERVAL_HOURS: int = 24


settings = Settings()
