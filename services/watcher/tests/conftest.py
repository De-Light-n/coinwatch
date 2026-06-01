import os

os.environ.setdefault("WATCHER_DB_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("WATCHER_REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("WATCHER_REDIS_URL_BACKEND", "redis://localhost:6379/1")
os.environ.setdefault("WATCHER_RABBITMQ_URL", "amqp://guest:guest@localhost/")
os.environ.setdefault("WATCHER_COINGECKO_BASE_URL", "https://api.coingecko.com/api/v3")
os.environ.setdefault("WATCHER_AUTH_SERVICE_URL", "http://localhost:8001")
os.environ.setdefault("WATCHER_INTERNAL_SERVICE_TOKEN", "test-token")

import pytest
from unittest.mock import AsyncMock, MagicMock
from redis.asyncio import Redis


@pytest.fixture
def mock_redis():
    redis_mock = AsyncMock(spec=Redis)

    async def async_get_none(*args, **kwargs):
        return None

    redis_mock.get.side_effect = async_get_none

    pipeline_mock = MagicMock()
    pipeline_mock.zremrangebyscore.return_value = pipeline_mock
    pipeline_mock.zcard.return_value = pipeline_mock
    pipeline_mock.zadd.return_value = pipeline_mock
    pipeline_mock.expire.return_value = pipeline_mock
    pipeline_mock.setex.return_value = pipeline_mock
    pipeline_mock.execute = AsyncMock(return_value=[None, 0, None, None])
    redis_mock.pipeline.return_value = pipeline_mock
    pipeline_mock.__aenter__ = AsyncMock(return_value=pipeline_mock)
    pipeline_mock.__aexit__ = AsyncMock(return_value=None)

    return redis_mock