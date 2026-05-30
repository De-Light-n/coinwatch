import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
import httpx

from app.coingecko.coingecko import CoinGeckoClient
from app.coingecko.exceptions import (
    CoinGeckoRateLimitError,
    CoinGeckoInvalidCoinError,
    CoinGeckoUnavailableError,
    CoinGeckoError,
)


# ─── fixtures ────────────────────────────────────────────────────
@pytest.fixture
def redis_mock():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock(return_value=True)
    r.setex = AsyncMock()

    pipe = MagicMock()                              # ← MagicMock, не AsyncMock
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.execute = AsyncMock(return_value=[None, 0, None, None])
    pipe.zremrangebyscore = MagicMock(return_value=pipe)
    pipe.zcard = MagicMock(return_value=pipe)
    pipe.zadd = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.setex = MagicMock(return_value=pipe)
    r.pipeline = MagicMock(return_value=pipe)       # ← MagicMock, не AsyncMock
    return r

@pytest.fixture
def client(redis_mock):
    return CoinGeckoClient(redis=redis_mock)


# ─── rate limit ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_not_exceeded(redis_mock):
    """count=24 is under the limit of 25 — should not raise."""
    pipe = redis_mock.pipeline.return_value
    pipe.execute = AsyncMock(return_value=[None, 24, None, None])
    client = CoinGeckoClient(redis=redis_mock)
    # Should complete without raising
    await client._check_rate_limit()


@pytest.mark.asyncio
async def test_rate_limit_exactly_at_limit_raises(redis_mock):
    """count == rate_limit_max (25) should raise."""
    pipe = redis_mock.pipeline.return_value
    pipe.execute = AsyncMock(return_value=[None, 25, None, None])
    client = CoinGeckoClient(redis=redis_mock)

    with pytest.raises(CoinGeckoRateLimitError):
        await client._check_rate_limit()


@pytest.mark.asyncio
async def test_rate_limit_exceeded_over_limit(redis_mock):
    pipe = redis_mock.pipeline.return_value
    pipe.execute = AsyncMock(return_value=[None, 30, None, None])
    client = CoinGeckoClient(redis=redis_mock)

    with pytest.raises(CoinGeckoRateLimitError):
        await client._check_rate_limit()


# ─── get_prices ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_prices_empty_list(client):
    result = await client.get_prices([])
    assert result == {}


@pytest.mark.asyncio
async def test_get_prices_cache_hit(client, redis_mock):
    redis_mock.get = AsyncMock(return_value="50000.00")

    result = await client.get_prices(["bitcoin"])

    assert "bitcoin" in result
    assert result["bitcoin"] == Decimal("50000.00")
    # No HTTP request should have been made
    client._client.request = AsyncMock()
    client._client.request.assert_not_called()


@pytest.mark.asyncio
async def test_get_prices_cache_miss_fetches_api(client, redis_mock):
    redis_mock.get = AsyncMock(return_value=None)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"bitcoin": {"usd": 60000}}
    mock_response.raise_for_status = MagicMock()

    with patch.object(client._client, "request", AsyncMock(return_value=mock_response)):
        result = await client.get_prices(["bitcoin"])

    assert "bitcoin" in result
    assert result["bitcoin"] == Decimal("60000")


@pytest.mark.asyncio
async def test_get_prices_partial_cache(client, redis_mock):
    """One coin in cache, another missing — only missing is fetched."""
    async def selective_get(key):
        if "bitcoin" in key:
            return "50000.00"
        return None

    redis_mock.get = selective_get

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ethereum": {"usd": 3000}}
    mock_response.raise_for_status = MagicMock()

    with patch.object(client._client, "request", AsyncMock(return_value=mock_response)) as mock_req:
        result = await client.get_prices(["bitcoin", "ethereum"])

    assert result["bitcoin"] == Decimal("50000.00")
    assert result["ethereum"] == Decimal("3000")
    # Only one API call for the missing coin
    mock_req.assert_called_once()
    assert "ethereum" in mock_req.call_args[1]["params"]["ids"]
    assert "bitcoin" not in mock_req.call_args[1]["params"]["ids"]


@pytest.mark.asyncio
async def test_get_prices_coin_missing_from_api_response(client, redis_mock):
    """If API doesn't return a coin, it's simply absent from the result."""
    redis_mock.get = AsyncMock(return_value=None)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}  # API returned nothing
    mock_response.raise_for_status = MagicMock()

    with patch.object(client._client, "request", AsyncMock(return_value=mock_response)):
        result = await client.get_prices(["unknowncoin"])

    assert "unknowncoin" not in result


# ─── _request_with_retry / HTTP errors ───────────────────────────

@pytest.mark.asyncio
async def test_404_raises_invalid_coin_error(client):
    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch.object(client._client, "request", AsyncMock(return_value=mock_response)):
        with pytest.raises(CoinGeckoInvalidCoinError):
            await client._request_with_retry("GET", "/coins/markets", {})


@pytest.mark.asyncio
async def test_500_raises_http_status_error_for_retry(client):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.request = MagicMock()

    with patch.object(client._client, "request", AsyncMock(return_value=mock_response)):
        with pytest.raises(httpx.HTTPStatusError):
            await client._request_with_retry("GET", "/coins/markets", {})


@pytest.mark.asyncio
async def test_429_raises_http_status_error_for_retry(client):
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.request = MagicMock()

    with patch.object(client._client, "request", AsyncMock(return_value=mock_response)):
        with pytest.raises(httpx.HTTPStatusError):
            await client._request_with_retry("GET", "/coins/markets", {})


@pytest.mark.asyncio
async def test_non_retryable_error_raises_coingecko_error(client):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.request = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Bad Request", request=mock_response.request, response=mock_response
    )

    with patch.object(client._client, "request", AsyncMock(return_value=mock_response)):
        with pytest.raises(CoinGeckoError):
            await client._request_with_retry("GET", "/coins/markets", {})


@pytest.mark.asyncio
async def test_circuit_breaker_open_raises_unavailable(client, redis_mock):
    """After the circuit breaker opens, _request should raise CoinGeckoUnavailableError."""
    import pybreaker

    with patch.object(
        client,
        "_request_with_retry",
        side_effect=pybreaker.CircuitBreakerError(),
    ):
        with pytest.raises(CoinGeckoUnavailableError):
            await client._request("GET", "/coins/markets", {})


# ─── get_market_data ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_market_data_empty_list(client):
    result = await client.get_market_data([])
    assert result == []


@pytest.mark.asyncio
async def test_get_market_data_returns_list(client, redis_mock):
    market_data = [{"id": "bitcoin", "current_price": 60000, "market_cap_rank": 1}]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = market_data
    mock_response.raise_for_status = MagicMock()

    with patch.object(client._client, "request", AsyncMock(return_value=mock_response)):
        result = await client.get_market_data(["bitcoin"])

    assert result == market_data


@pytest.mark.asyncio
async def test_get_market_data_invalid_coin_raises(client):
    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch.object(client._client, "request", AsyncMock(return_value=mock_response)):
        with pytest.raises(CoinGeckoInvalidCoinError):
            await client.get_market_data(["fakecoin"])


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
async def test_validate_asset_empty_results(client):
    client.search_coins = AsyncMock(return_value=[])
    result = await client.validate_asset("bitcoin")
    assert result is False


@pytest.mark.asyncio
async def test_validate_asset_case_insensitive(client):
    client.search_coins = AsyncMock(return_value=[{"id": "bitcoin", "name": "Bitcoin"}])
    result = await client.validate_asset("BITCOIN")
    assert result is True


@pytest.mark.asyncio
async def test_validate_asset_exception_returns_false(client):
    client.search_coins = AsyncMock(side_effect=Exception("network error"))
    result = await client.validate_asset("bitcoin")
    assert result is False


@pytest.mark.asyncio
async def test_validate_asset_partial_match_not_accepted(client):
    """'bit' must not match 'bitcoin' — exact id match required."""
    client.search_coins = AsyncMock(return_value=[{"id": "bitcoin", "name": "Bitcoin"}])
    result = await client.validate_asset("bit")
    assert result is False


# ─── search_coins ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_coins_returns_list(client):
    search_result = {"coins": [{"id": "bitcoin", "name": "Bitcoin"}]}

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = search_result
    mock_response.raise_for_status = MagicMock()

    with patch.object(client._client, "request", AsyncMock(return_value=mock_response)):
        result = await client.search_coins("bitcoin")

    assert result == [{"id": "bitcoin", "name": "Bitcoin"}]


@pytest.mark.asyncio
async def test_search_coins_empty_response(client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"coins": []}
    mock_response.raise_for_status = MagicMock()

    with patch.object(client._client, "request", AsyncMock(return_value=mock_response)):
        result = await client.search_coins("zzznomatch")

    assert result == []


# ─── list_all_coins ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_all_coins_cache_hit(client, redis_mock):
    import json
    coins = [{"id": "bitcoin"}, {"id": "ethereum"}]
    redis_mock.get = AsyncMock(return_value=json.dumps(coins))

    result = await client.list_all_coins()

    assert result == coins
    # No HTTP request
    client._client.request = AsyncMock()
    client._client.request.assert_not_called()


@pytest.mark.asyncio
async def test_list_all_coins_cache_miss_fetches_and_stores(client, redis_mock):
    import json
    redis_mock.get = AsyncMock(return_value=None)
    coins = [{"id": "bitcoin"}, {"id": "ethereum"}]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = coins
    mock_response.raise_for_status = MagicMock()

    with patch.object(client._client, "request", AsyncMock(return_value=mock_response)):
        result = await client.list_all_coins()

    assert result == coins
    redis_mock.setex.assert_called_once()
    args = redis_mock.setex.call_args[0]
    assert args[0] == "cg:coins_list"
    assert args[1] == 86400  # 24h TTL


# ─── close ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_close_shuts_down_http_client(client):
    with patch.object(client._client, "aclose", AsyncMock()) as mock_close:
        await client.close()
        mock_close.assert_called_once()