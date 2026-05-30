import json
import time
import logging
from decimal import Decimal
from typing import List, Dict, Any, Optional

import httpx
import pybreaker
from redis.asyncio import Redis
from tenacity import retry, stop_after_attempt, wait_exponential

from app.coingecko.exceptions import (
    CoinGeckoError,
    CoinGeckoUnavailableError,
    CoinGeckoRateLimitError,
    CoinGeckoInvalidCoinError,
)

logger = logging.getLogger(__name__)


# =========================================================
# CIRCUIT BREAKER
# =========================================================

circuit_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    exclude=[CoinGeckoInvalidCoinError],
)


# =========================================================
# CLIENT
# =========================================================

class CoinGeckoClient:
    def __init__(
        self,
        redis: Redis,
        base_url: str = "https://api.coingecko.com/api/v3",
    ):
        self.redis = redis
        self.base_url = base_url.rstrip("/")

        self.rate_limit_max = 25
        self.rate_limit_window = 60

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
        )

    # =====================================================
    # CLOSE
    # =====================================================
    async def close(self):
        await self._client.aclose()

    # =====================================================
    # RATE LIMIT (SLIDING WINDOW)
    # =====================================================
    async def _check_rate_limit(self):
        now = time.time()
        key = "cg:ratelimit:window"
        cutoff = now - self.rate_limit_window

        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, self.rate_limit_window)
            _, current, _, _ = await pipe.execute()

        if current >= self.rate_limit_max:
            raise CoinGeckoRateLimitError("Rate limit exceeded")

    # =====================================================
    # CORE REQUEST
    # =====================================================
    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        await self._check_rate_limit()

        try:
            return await self._request_with_retry(method, path, params)
        except pybreaker.CircuitBreakerError:
            raise CoinGeckoUnavailableError("CoinGecko circuit breaker open")

    # =====================================================
    # RETRY (ONLY 5xx + 429)
    # =====================================================
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    @circuit_breaker
    async def _request_with_retry(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        url = f"{self.base_url}{path}"

        response = await self._client.request(
            method,
            url,
            params=params,
        )

        # ---------------- 404 ----------------
        if response.status_code == 404:
            raise CoinGeckoInvalidCoinError("Coin not found")

        # ---------------- RETRYABLE ERRORS ----------------
        if response.status_code in (429, 500, 502, 503, 504):
            raise httpx.HTTPStatusError(
                "Retryable error",
                request=response.request,
                response=response,
            )

        # ---------------- NON-RETRYABLE ----------------
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise CoinGeckoError(f"CoinGecko error: {exc.response.status_code}")

        return response.json()

    # =====================================================
    # GET PRICES (BATCH + CACHE)
    # =====================================================
    async def get_prices(
        self,
        coin_ids: List[str],
        vs_currency: str = "usd",
    ) -> Dict[str, Decimal]:

        if not coin_ids:
            return {}

        result: Dict[str, Decimal] = {}
        missing: List[str] = []

        # ---- CACHE HIT/MISS ----
        for coin_id in coin_ids:
            key = f"cg:price:{vs_currency}:{coin_id}"
            cached = await self.redis.get(key)

            if cached:
                result[coin_id] = Decimal(cached)
            else:
                missing.append(coin_id)

        # ---- FETCH ONLY MISSING ----
        if missing:
            data = await self._request(
                "GET",
                "/simple/price",
                {
                    "ids": ",".join(missing),
                    "vs_currencies": vs_currency,
                },
            )

            async with self.redis.pipeline() as pipe:
                for coin_id in missing:
                    price = data.get(coin_id, {}).get(vs_currency)

                    if price is not None:
                        dec = Decimal(str(price))
                        result[coin_id] = dec

                        pipe.setex(
                            f"cg:price:{vs_currency}:{coin_id}",
                            30,
                            str(dec),
                        )

                await pipe.execute()

        return result

    # =====================================================
    # MARKET DATA
    # =====================================================
    async def get_market_data(self, coin_ids: List[str]) -> List[dict]:
        if not coin_ids:
            return []

        return await self._request(
            "GET",
            "/coins/markets",
            {
                "vs_currency": "usd",
                "ids": ",".join(coin_ids),
            },
        )

    # =====================================================
    # SEARCH
    # =====================================================
    async def search_coins(self, query: str) -> List[dict]:
        data = await self._request(
            "GET",
            "/search",
            {"query": query},
        )
        return data.get("coins", [])

    # =====================================================
    # LIST ALL COINS (CACHE 24h)
    # =====================================================
    async def list_all_coins(self) -> List[dict]:
        key = "cg:coins_list"

        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)

        coins = await self._request("GET", "/coins/list")

        await self.redis.setex(
            key,
            86400,
            json.dumps(coins),
        )

        return coins
    

    async def validate_asset(self, asset_id: str) -> bool:
        try:
            coins = await self.search_coins(asset_id)

            return any(
                c.get("id", "").lower() == asset_id.lower()
                for c in coins
            )
        except Exception:
            return False