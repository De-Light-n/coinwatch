from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

class DatabaseManager:
    def __init__(self, database_url: str, echo: bool = False):
        self.engine = create_async_engine(database_url, echo=echo)
        self.session_factory = async_sessionmaker(
            bind=self.engine, 
            autocommit=False, 
            autoflush=False, 
            expire_on_commit=False,
            class_=AsyncSession
        )

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_factory() as session:
            try:
                yield session
            finally:
                await session.close()