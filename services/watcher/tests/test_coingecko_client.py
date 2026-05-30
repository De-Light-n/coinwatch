import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
 
from app.coingecko.coingecko import CoinGeckoClient
from app.coingecko.exceptions import (
    CoinGeckoRateLimitError,
    CoinGeckoInvalidCoinError,
    CoinGeckoUnavailableError,
)
 
 
@pytest.fixture
def redis_mock():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.pipeline = MagicMock()
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.execute = AsyncMock(return_value=[0, 0, 0, 0])
    pipe.zremrangebyscore = MagicMock()
    pipe.zcard = MagicMock()
    pipe.zadd = MagicMock()
    pipe.expire = MagicMock()
    pipe.setex = MagicMock()
    r.pipeline.return_value = pipe
    return r
 
 
@pytest.fixture
def client(redis_mock):
    return CoinGeckoClient(redis=redis_mock)
 
 
# ─── rate limit ──────────────────────────────────────────────────
 
@pytest.mark.asyncio
async def test_rate_limit_exceeded(redis_mock):
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.execute = AsyncMock(return_value=[0, 25, 1, 1])
    pipe.zremrangebyscore = MagicMock()
    pipe.zcard = MagicMock()
    pipe.zadd = MagicMock()
    pipe.expire = MagicMock()
    redis_mock.pipeline.return_value = pipe
 
    client = CoinGeckoClient(redis=redis_mock)
    with pytest.raises(CoinGeckoRateLimitError):
        await client._check_rate_limit()
 
 
# ─── get_prices cache ────────────────────────────────────────────
 
@pytest.mark.asyncio
async def test_get_prices_cache_hit(client, redis_mock):
    redis_mock.get = AsyncMock(return_value="50000.00")
 
    result = await client.get_prices(["bitcoin"])
 
    assert "bitcoin" in result
    assert result["bitcoin"] == Decimal("50000.00")
 
 
@pytest.mark.asyncio
async def test_get_prices_empty(client):
    result = await client.get_prices([])
    assert result == {}
 
 
# ─── validate_asset ──────────────────────────────────────────────
 
@pytest.mark.asyncio
async def test_validate_asset_found(client):
    client.search_coins = AsyncMock(return_value=[{"id": "bitcoin", "name": "Bitcoin"}])
    result = await client.validate_asset("bitcoin")
    assert result is True
 
 
@pytest.mark.asyncio
async def test_validate_asset_not_found(client):
    client.search_coins = AsyncMock(return_value=[{"id": "ethereum", "name": "Ethereum"}])
    result = await client.validate_asset("fakecoin")
    assert result is False
 
 
@pytest.mark.asyncio
async def test_validate_asset_exception(client):
    client.search_coins = AsyncMock(side_effect=Exception("network error"))
    result = await client.validate_asset("bitcoin")
    assert result is False
 
 
# ─── get_market_data ─────────────────────────────────────────────
 
@pytest.mark.asyncio
async def test_get_market_data_empty(client):
    result = await client.get_market_data([])
    assert result == []
 
