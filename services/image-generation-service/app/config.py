from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "image-generation-service"
    API_PREFIX: str = "/api/v1/images"
    ROOT_PATH: str = ""
    DATABASE_URL: str = "postgresql+asyncpg://adgen:changeme_in_production@postgres:5432/adgen_ai"
    REDIS_URL: str = "redis://redis:6379/0"
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "adgen-auth"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
