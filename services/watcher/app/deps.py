from typing import AsyncGenerator

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.auth import AuthClient
from app.clients.coingecko import CoinGeckoClient
from app.crud.watcher import WatchCrud
from app.db import async_session_factory, get_redis
from app.services.watcher import WatcherService


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis_client() -> AsyncGenerator[Redis, None]:
    redis = await get_redis()
    try:
        yield redis
    finally:
        await redis.close()


async def get_auth_client() -> AsyncGenerator[AuthClient, None]:
    client = AuthClient()
    try:
        yield client
    finally:
        await client.aclose()


async def get_coingecko_client(
    redis: Redis = Depends(get_redis_client),
) -> AsyncGenerator[CoinGeckoClient, None]:
    client = CoinGeckoClient(redis=redis)
    try:
        yield client
    finally:
        await client.aclose()


async def get_watcher_service(
    session: AsyncSession = Depends(get_session),
    auth: AuthClient = Depends(get_auth_client),
    coingecko: CoinGeckoClient = Depends(get_coingecko_client),
) -> WatcherService:
    crud = WatchCrud(session=session)
    return WatcherService(auth=auth, coingecko=coingecko, crud=crud)