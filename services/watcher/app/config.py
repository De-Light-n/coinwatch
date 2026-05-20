import os
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = os.getenv("SERVICE_ENV_PREFIX", "WATCHER_")

class Settings(BaseSettings):
    PROJECT_NAME: str = "watcher"
    ENV: str = "development"
    DEBUG: bool = True
    DB_URL: str 
    REDIS_URL: str 
    RABBITMQ_URL: str 
    COINGECKO_BASE_URL: str
    AUTH_SERVICE_URL: str 
    SERVICE_TOKEN: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="WATCHER_",
        extra="ignore"
    )

settings = Settings()