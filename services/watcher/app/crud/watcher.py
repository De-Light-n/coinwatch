from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.watch import Watch
from app.schemas.watcher import WatcherCreate,WatchResponseSchema


class WatchCrud:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: int,
        data: WatcherCreate,
        interval_seconds: int,
    ) -> WatchResponseSchema:
        watch = Watch(
            user_id=user_id,
            name=data.name,
            asset=data.asset,
            condition_type=data.condition_type,
            threshold=data.threshold,
            interval_seconds=interval_seconds,
        )
        self.session.add(watch)
        await self.session.commit()
        await self.session.refresh(watch)
        return watch

    async def count_active(self, user_id: int) -> int:
        stmt = select(func.count()).where(
            Watch.user_id == user_id,
            Watch.is_active == True,
        )
        res = await self.session.execute(stmt)
        return res.scalar()