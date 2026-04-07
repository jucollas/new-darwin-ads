from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    SERVICE_NAME: str = "analytics-service"
    API_PREFIX: str = "/api/v1/metrics"
    ROOT_PATH: str = ""
    DATABASE_URL: str = "postgresql+asyncpg://adgen:changeme_in_production@postgres:5432/adgen_ai"
    REDIS_URL: str = "redis://redis:6379/0"
    JWT_SECRET_KEY: str = "changeme"
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "adgen-ai"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Meta Ads
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    META_ACCESS_TOKEN: str = ""
    META_AD_ACCOUNT_ID: str = ""
    META_PAGE_ID: str = ""
    META_WHATSAPP_NUMBER: str = ""

    # Analytics-specific
    METRICS_COLLECTION_INTERVAL_HOURS: int = 6
    METRICS_LOOKBACK_DAYS: int = 7

    # Inter-service
    PUBLISHING_SERVICE_URL: str = "http://publishing-service:8004"
    CAMPAIGN_SERVICE_URL: str = "http://campaign-service:8001"


settings = Settings()
