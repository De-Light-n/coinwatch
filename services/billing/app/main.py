from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.config import settings
from app.logging import setup_logging
from app.routers import billing, webhook
from fastapi.middleware.cors import CORSMiddleware

logger = setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Service initialization", service=settings.PROJECT_NAME, env=settings.ENV)
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",  # ← додай це
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(billing.router, prefix="/billing", tags=["billing"])
app.include_router(webhook.router, prefix="/webhooks", tags=["webhooks"])

@app.get("/health", tags=["infrastructure"])
async def health_check():
    return {"status": "ok", "service": settings.PROJECT_NAME}