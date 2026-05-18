from pydantic_settings import BaseSettings

class BaseServiceSettings(BaseSettings):
    PROJECT_NAME: str = "Coinwatch Service"
    ENV: str = "development"
    DEBUG: bool = True
    
    DATABASE_URL: str = "postgresql+asyncpg://postgres:super_secret_password_123@localhost:5432/postgres"

    class Config:
        env_file = ".env"
        extra = "ignore"