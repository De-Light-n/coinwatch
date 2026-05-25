from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.watch import Watch

class WatchRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def count_active_by_user(self, user_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(Watch)
            .where(Watch.user_id == user_id, Watch.is_active == True)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def create(self, watch: Watch) -> Watch:
        self.session.add(watch)
        await self.session.commit()
        await self.session.refresh(watch)
        return watch

    async def get_by_id_and_user(self, watch_id: UUID, user_id: str) -> Optional[Watch]:
        stmt = select(Watch).where(Watch.id == watch_id, Watch.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi(
        self, 
        user_id: str, 
        is_active: Optional[bool] = None, 
        asset: Optional[str] = None, 
        limit: int = 10, 
        offset: int = 0
    ) -> List[Watch]:
        stmt = select(Watch).where(Watch.user_id == user_id)
        
        if is_active is not None:
            stmt = stmt.where(Watch.is_active == is_active)
        if asset is not None:
            stmt = stmt.where(Watch.asset == asset)
            
        stmt = stmt.limit(limit).offset(offset).order_by(Watch.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, watch: Watch) -> Watch:
        await self.session.commit()
        await self.session.refresh(watch)
        return watch

    async def delete(self, watch: Watch, hard_delete: bool = False) -> None:
        if hard_delete:
            await self.session.delete(watch)
        else:
            watch.is_active = False
        await self.session.commit()