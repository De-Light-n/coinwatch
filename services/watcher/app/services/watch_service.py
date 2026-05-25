from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, status
from app.models.watch import Watch
from app.schemas.watcher import WatcherCreate, WatcherUpdate
from app.repository.watch_repository import WatchRepository
from app.clients.auth import AuthClient
from app.clients.coingecko import CoinGeckoClient

class WatchService:
    def __init__(self, repo: WatchRepository, auth_client: AuthClient, coingecko_client: CoinGeckoClient):
        self.repo = repo
        self.auth_client = auth_client
        self.coingecko_client = coingecko_client

    async def create_watch(self, data: WatcherCreate, user_id: str) -> Watch:
        quota = await self.auth_client.get_user_quota(user_id)
        
        active_count = await self.repo.count_active_by_user(user_id)
        if active_count >= quota.max_watches:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Quota exceeded"
            )

        asset_exists = await self.coingecko_client.validate_asset(data.asset)
        if not asset_exists:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Asset '{data.asset}' does not exist in CoinGecko"
            )

        watch = Watch(
            user_id=user_id,
            name=data.name,
            asset=data.asset,
            condition_type=data.condition_type,
            threshold=data.threshold,
            interval_seconds=quota.check_interval_seconds,
        )
        
        return await self.repo.create(watch)

    async def get_watch_or_404(self, watch_id: UUID, user_id: str) -> Watch:
        watch = await self.repo.get_by_id_and_user(watch_id, user_id)
        if not watch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watch not found"
            )
        return watch

    async def get_user_watches(
        self, 
        user_id: str, 
        is_active: Optional[bool], 
        asset: Optional[str], 
        limit: int, 
        offset: int
    ) -> List[Watch]:
        return await self.repo.get_multi(
            user_id=user_id, 
            is_active=is_active, 
            asset=asset, 
            limit=limit, 
            offset=offset
        )

    async def update_watch(self, watch_id: UUID, user_id: str, data: WatcherUpdate) -> Watch:
        watch = await self.get_watch_or_404(watch_id, user_id)
        
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(watch, key, value)
            
        return await self.repo.update(watch)

    async def delete_watch(self, watch_id: UUID, user_id: str) -> None:
        watch = await self.get_watch_or_404(watch_id, user_id)
        await self.repo.delete(watch, hard_delete=False)

    async def search_coins(self, query: str):
        return await self.coingecko_client.search(query)