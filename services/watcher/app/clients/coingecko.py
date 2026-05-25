import httpx
import json
from redis.asyncio import Redis
from fastapi import HTTPException, status

class CoinGeckoClient:
    CACHE_KEY = "coingecko:coins_list"
    CACHE_TTL = 86400  

    def __init__(self, redis: Redis):
        self.redis = redis
        self.base_url = "https://api.coingecko.com/api/v3"

    async def validate_asset(self, asset_id: str) -> bool:
        cached_list = await self.redis.get(self.CACHE_KEY)
        
        if cached_list:
            coins = json.loads(cached_list)
        else:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/coins/list")
                if response.status_code != 200:
                    raise httpx.HTTPStatusError("CoinGecko API error", request=response.request, response=response)
                
                coins = response.json()
                await self.redis.setex(self.CACHE_KEY, self.CACHE_TTL, json.dumps(coins))

        return any(coin.get('id') == asset_id for coin in coins)

    async def search(self, query: str) -> dict:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/search",
                    params={"query": query}
                )
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Failed to fetch search data from CoinGecko"
                    )
                
                return response.json()
                
            except httpx.RequestError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"CoinGecko connection error: {exc}"
                )