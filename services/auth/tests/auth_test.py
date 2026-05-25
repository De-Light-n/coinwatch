import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from sqlalchemy import text
from app.db import AsyncSessionLocal
from sqlalchemy import select
from app.models.models import User

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

async def make_user_admin(email: str):
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE users SET role = 'ADMIN'::userrole WHERE email = :email"),
            {"email": email}
        )
        await db.commit()
@pytest.mark.asyncio
async def test_get_me_happy_path(client):
    test_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={"email": test_email, "password": "securepassword123", "full_name": "Test User"})
    login = await client.post("/auth/login", json={"email": test_email, "password": "securepassword123"})
    token = login.json()["access_token"]

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == test_email
    assert response.json()["full_name"] == "Test User"
    assert "password_hash" not in response.json()

@pytest.mark.asyncio
async def test_soft_delete_and_login_prevention(client):
    test_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={"email": test_email, "password": "securepassword123"})
    login = await client.post("/auth/login", json={"email": test_email, "password": "securepassword123"})
    token = login.json()["access_token"]

    delete_response = await client.delete("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert delete_response.status_code == 200

    login_after_delete = await client.post("/auth/login", json={"email": test_email, "password": "securepassword123"})
    assert login_after_delete.status_code == 401

@pytest.mark.asyncio
async def test_admin_rbac_protection(client):
    test_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={"email": test_email, "password": "securepassword123"})
    login = await client.post("/auth/login", json={"email": test_email, "password": "securepassword123"})
    token = login.json()["access_token"]

    response = await client.get("/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_admin_endpoints_happy_path(client):
    test_email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={"email": test_email, "password": "securepassword123"})
    await make_user_admin(test_email)
    
    login = await client.post("/auth/login", json={"email": test_email, "password": "securepassword123"})
    token = login.json()["access_token"]

    users_response = await client.get("/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert users_response.status_code == 200
    assert len(users_response.json()) > 0
    
    first_user_id = users_response.json()[0]["id"]
    update_response = await client.patch(
        f"/auth/users/{first_user_id}", 
        json={"is_active": False}, 
        headers={"Authorization": f"Bearer {token}"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["is_active"] is False   