# conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from redis.asyncio import Redis

@pytest.fixture
def mock_redis():
    """Надійний мок для Redis клієнта з підтримкою асинхронних методів."""
    redis_mock = AsyncMock(spec=Redis)
    
    # Використовуємо окрему асинхронну функцію-заглушку для методу get, 
    # щоб повертати корутину, яка розгортається в None
    async def async_get_none(*args, **kwargs):
        return None
    redis_mock.get.side_effect = async_get_none

    # Створюємо синхронний мок для самого об'єкта pipeline
    pipeline_mock = MagicMock()
    
    # Ланцюжкові синхронні методи повертають сам об'єкт pipeline
    pipeline_mock.zremrangebyscore.return_value = pipeline_mock
    pipeline_mock.zcard.return_value = pipeline_mock
    pipeline_mock.zadd.return_value = pipeline_mock
    pipeline_mock.expire.return_value = pipeline_mock
    pipeline_mock.setex.return_value = pipeline_mock
    
    # execute() повертає результат асинхронно
    pipeline_mock.execute = AsyncMock(return_value=[None, 0, None, None])
    
    # Налаштовуємо контекстний менеджер та метод pipeline()
    redis_mock.pipeline.return_value = pipeline_mock
    pipeline_mock.__aenter__ = AsyncMock(return_value=pipeline_mock)
    pipeline_mock.__aexit__ = AsyncMock(return_value=None)
    
    return redis_mock