from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "dev-auth-service"
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "adgen-auth"
    ENVIRONMENT: str = "development"
    DATA_DIR: str = "/app/data"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
