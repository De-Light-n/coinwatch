import httpx


class AuthClient:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            base_url="http://auth-service:8000",
            timeout=5.0,
        )

    async def get_quota(self, user_id: str) -> dict[str, int]:
        r = await self.client.get(f"/internal/users/{user_id}/quota")
        r.raise_for_status()
        return r.json()

    async def aclose(self) -> None:
        await self.client.aclose()