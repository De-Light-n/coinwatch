from fastapi import HTTPException

from app.clients.auth import AuthClient
from app.clients.coingecko import CoinGeckoClient
from app.crud.watcher import WatchCrud
from app.schemas.watcher import WatcherCreate,WatchResponseSchema


class WatcherService:
    def __init__(
        self,
        auth: AuthClient,
        coingecko: CoinGeckoClient,
        crud: WatchCrud,
    ) -> None:
        self.auth = auth
        self.coingecko = coingecko
        self.crud = crud

    # async def create_watch(
    #     self,
    #     user_id: int,
    #     data: WatcherCreate,
    # ) -> WatchResponseSchema:
    #     quota: dict[str, int] = await self.auth.get_quota(user_id)
    #     active: int = await self.crud.count_active(user_id)
    #     if active >= quota["max_watches"]:
    #         raise HTTPException(403, "Quota exceeded")
    #     valid: bool = await self.coingecko.validate_coin(data.asset)
    #     if not valid:
    #         raise HTTPException(400, "Invalid asset")
    #     return await self.crud.create(
    #         user_id=user_id,
    #         data=data,
    #         interval_seconds=quota["interval_seconds"],
    #     )

    async def create_watch(
    self,
    user_id: int,
        data: WatcherCreate,
    ) -> WatchResponseSchema:
        # TODO: замінити коли auth-service буде готовий
        quota: dict[str, int] = {
            "max_watches": 10,
            "interval_seconds": 60,
        }
        active: int = await self.crud.count_active(user_id)
        if active >= quota["max_watches"]:
            raise HTTPException(403, "Quota exceeded")
        valid: bool = await self.coingecko.validate_coin(data.asset)
        if not valid:
            raise HTTPException(400, "Invalid asset")
        return await self.crud.create(
            user_id=user_id,
            data=data,
            interval_seconds=quota["interval_seconds"],
        )