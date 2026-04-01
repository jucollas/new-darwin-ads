from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "image-generation-service"
    API_PREFIX: str = "/api/v1/images"
    ROOT_PATH: str = ""
    REDIS_URL: str = "redis://redis:6379/0"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"

    # Google Cloud
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    GCS_BUCKET_NAME: str = ""

    # Image defaults
    DEFAULT_ASPECT_RATIO: str = "1:1"
    IMAGE_QUALITY: str = "hd"

    # Service communication
    CAMPAIGN_SERVICE_URL: str = "http://campaign-service:8001"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
