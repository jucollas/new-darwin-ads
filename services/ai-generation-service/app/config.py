from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "ai-generation-service"
    API_PREFIX: str = "/api/v1/ai"
    ROOT_PATH: str = ""
    REDIS_URL: str = "redis://redis:6379/0"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 4096
    OPENAI_TEMPERATURE: float = 0.8
    OPENAI_TIMEOUT: int = 60

    # Inter-service
    CAMPAIGN_SERVICE_URL: str = "http://campaign-service:8001"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
