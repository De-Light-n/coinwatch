import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.watcher import router
from app.config import settings
from app.coingecko.exceptions import (
    CoinGeckoRateLimitError,
    CoinGeckoUnavailableError,
)
from app.db import close_db, close_redis


structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_starting", service=settings.PROJECT_NAME)

    yield

    logger.info("service_shutting_down", service=settings.PROJECT_NAME)

    await close_db()
    await close_redis()


app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    root_path="/watcher",
)


@app.exception_handler(CoinGeckoRateLimitError)
async def rate_limit_handler(request: Request, exc: CoinGeckoRateLimitError):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "CoinGecko rate limit exceeded"},
    )


@app.exception_handler(CoinGeckoUnavailableError)
async def unavailable_handler(request: Request, exc: CoinGeckoUnavailableError):
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "CoinGecko service temporarily unavailable"},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
    }