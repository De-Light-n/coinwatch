import os
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = os.getenv("SERVICE_ENV_PREFIX", "AUTH_")

class Settings(BaseSettings):
    PROJECT_NAME: str = "auth" 
    ENV: str = "development"
    DEBUG: bool = True
    DB_URL: str = "postgresql+asyncpg://postgres:super_secret_password_123@localhost:5432/auth_db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix=ENV_PREFIX,
        extra="ignore"
    )

settings = Settings()