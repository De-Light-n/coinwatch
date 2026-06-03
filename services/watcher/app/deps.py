from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.db import async_session_factory, redis
from app.clients.auth import AuthClient
from app.coingecko.coingecko import CoinGeckoClient
from app.repository.watch_repository import WatchRepository
from app.services.watch_service import WatchService


security = HTTPBearer(auto_error=False)


# ---------------- DB ----------------

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def get_redis() -> Redis:
    return redis


# ---------------- AUTH ----------------

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_client: AuthClient = Depends(),
):
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )

    return await auth_client.get_current_user(credentials.credentials)


# ---------------- COINGECKO ----------------

_coingecko_client = None


async def get_coingecko_client(
    redis_client: Redis = Depends(get_redis),
) -> CoinGeckoClient:
    global _coingecko_client

    if _coingecko_client is None:
        _coingecko_client = CoinGeckoClient(redis=redis_client)

    return _coingecko_client


# ---------------- SERVICE ----------------

async def get_watch_service(
    session: AsyncSession = Depends(get_session),
    auth_client: AuthClient = Depends(),
    coingecko_client: CoinGeckoClient = Depends(get_coingecko_client),
):
    repo = WatchRepository(session)

    return WatchService(
        repo=repo,
        auth_client=auth_client,
        coingecko_client=coingecko_client,
    )