from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.clients.auth import AuthClient
from app.clients.coingecko import CoinGeckoClient
from app.db import async_session_factory, get_redis
from app.services.watch_service import WatchService
from app.repository.watch_repository import WatchRepository

security = HTTPBearer(auto_error=False)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_client: AuthClient = Depends()
):
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token"
        )
    
    return await auth_client.get_current_user(credentials.credentials)

async def get_watch_service(
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    auth_client: AuthClient = Depends()
) -> WatchService:
    repo = WatchRepository(session)
    coingecko_client = CoinGeckoClient(redis=redis)
    return WatchService(repo=repo, auth_client=auth_client, coingecko_client=coingecko_client)