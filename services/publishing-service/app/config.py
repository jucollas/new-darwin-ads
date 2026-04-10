from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    SERVICE_NAME: str = "publishing-service"
    API_PREFIX: str = "/api/v1/publish"
    ROOT_PATH: str = ""
    DATABASE_URL: str = "postgresql+asyncpg://adgen:changeme_in_production@postgres:5432/adgen_ai"
    REDIS_URL: str = "redis://redis:6379/0"
    JWT_SECRET_KEY: str = "changeme"
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "adgen-ai"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    ENVIRONMENT: str = "development"

    # Meta Ads
    META_ACCESS_TOKEN: str = ""
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    META_API_VERSION: str = "v25.0"
    META_GRAPH_API_BASE_URL: str = "https://graph.facebook.com"
    META_REDIRECT_URI: str = ""
    META_TOKEN_ENCRYPTION_KEY: str = ""

    # Default ad account / page
    AD_ACCOUNT_ID: str = ""
    PAGE_ID: str = ""
    BUSINESS_MANAGER_ID: str = ""
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    WHATSAPP_DEFAULT_PHONE_NUMBER: str | None = None

    # Meta defaults
    META_DEFAULT_CURRENCY: str = "USD"
    META_DEFAULT_BID_STRATEGY: str = "LOWEST_COST_WITHOUT_CAP"
    META_DEFAULT_BILLING_EVENT: str = "IMPRESSIONS"
    META_DEFAULT_OPTIMIZATION_GOAL: str = "CONVERSATIONS"
    META_DEFAULT_CAMPAIGN_OBJECTIVE: str = "OUTCOME_ENGAGEMENT"

    # Inter-service
    CAMPAIGN_SERVICE_URL: str = "http://campaign-service:8001"


settings = Settings()
