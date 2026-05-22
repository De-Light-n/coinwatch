from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.shared.config import BaseServiceSettings

def create_app(settings: BaseServiceSettings) -> FastAPI:
    """Універсальний конструктор FastAPI додатка."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        debug=settings.DEBUG,
        docs_url="/docs",
        redoc_url="/redoc"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["Infrastructure"])
    async def health_check():
        return {
            "status": "healthy",
            "service": settings.PROJECT_NAME,
            "environment": settings.ENV
        }

    return app