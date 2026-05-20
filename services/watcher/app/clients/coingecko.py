import httpx
import json
from redis.asyncio import Redis


class CoinGeckoClient:
    def __init__(self, redis: Redis) -> None:
        self.client = httpx.AsyncClient(
            base_url="https://api.coingecko.com/api/v3",
            timeout=10.0,
        )
        self.redis = redis

    async def get_coin_list(self) -> list[dict[str, str]]:
        cached = await self.redis.get("coins:list")
        if cached:
            return json.loads(cached)
        r = await self.client.get("/coins/list")
        data: list[dict[str, str]] = r.json()
        await self.redis.set(
            "coins:list",
            json.dumps(data),
            ex=86400,
        )
        return data

    async def validate_coin(self, asset: str) -> bool:
        coins = await self.get_coin_list()
        return any(c["id"] == asset for c in coins)

    async def aclose(self) -> None:
        await self.client.aclose()