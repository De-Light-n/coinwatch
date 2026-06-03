import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = os.getenv("SERVICE_ENV_PREFIX", "BILLING_")

# Виходимо з app/ → billing/ → services/ → coinwatch/ (корінь)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

class Settings(BaseSettings):
    PROJECT_NAME: str = "billing"
    ENV: str = "development"
    DEBUG: bool = True

    DB_URL: str
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    STRIPE_PRO_PRICE_ID: str
    STRIPE_BUSINESS_PRICE_ID: str
    CHECKOUT_SUCCESS_URL: str = "http://localhost:3000/success?session_id={CHECKOUT_SESSION_ID}"
    CHECKOUT_CANCEL_URL: str = "http://localhost:3000/cancel"
    PORTAL_RETURN_URL: str = "http://localhost:3000/account"
    RABBITMQ_URL: str
    AUTH_SERVICE_URL: str
    SERVICE_TOKEN: str

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_prefix=ENV_PREFIX,
        extra="ignore"
    )

settings = Settings()