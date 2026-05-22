import os
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = os.getenv("SERVICE_ENV_PREFIX", "AUTH_")

class Settings(BaseSettings):
    PROJECT_NAME: str = "auth" 
    ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str
    REDIS_URL: str
    INTERNAL_SERVICE_TOKEN: str
    DATABASE_URL: str
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()