import pytest
import uuid
import json
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings
from app.api.internal import redis_client

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_internal_unauthorized(client):
    response = await client.get(f"/internal/users/{uuid.uuid4()}/quota")
    assert response.status_code in [401, 422]

@pytest.mark.asyncio
async def test_quota_cache_miss_and_hit(client):
    test_email = f"quota_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={"email": test_email, "password": "securepassword123"})
    login = await client.post("/auth/login", json={"email": test_email, "password": "securepassword123"})
    
    token = login.json()["access_token"]
    verify_res = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_id = verify_res.json()["id"]

    headers = {"X-Service-Token": settings.INTERNAL_SERVICE_TOKEN}
    
    await redis_client.delete(f"quota:{user_id}")
    response = await client.get(f"/internal/users/{user_id}/quota", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["plan"] == "free"
    assert data["limits"]["max_watches"] == 3
    
   
    cached = await redis_client.get(f"quota:{user_id}")
    assert cached is not None
    
    fake_quota = data.copy()
    fake_quota["plan"] = "pro"
    await redis_client.set(f"quota:{user_id}", json.dumps(fake_quota))
    
    response_hit = await client.get(f"/internal/users/{user_id}/quota", headers=headers)
    assert response_hit.json()["plan"] == "pro"

@pytest.mark.asyncio
async def test_verify_token_internal(client):
    test_email = f"verify_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={"email": test_email, "password": "securepassword123"})
    login = await client.post("/auth/login", json={"email": test_email, "password": "securepassword123"})
    token = login.json()["access_token"]

    headers = {"X-Service-Token": settings.INTERNAL_SERVICE_TOKEN}
    response = await client.post("/internal/auth/verify-token", json={"access_token": token}, headers=headers)
    
    assert response.status_code == 200
    assert response.json()["is_active"] is True