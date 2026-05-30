import pytest
import respx
from httpx import Response, RequestError
from fastapi import HTTPException

from app.clients.auth import AuthClient, UserQuotaResponse

pytestmark = pytest.mark.anyio

@respx.mock
async def test_get_current_user_success():
    client = AuthClient()
    token = "valid_jwt_token"
    
    route = respx.post(f"{client.base_url}/internal/auth/verify-token").mock(
        return_value=Response(
            status_code=200, 
            json={"user_id": "user_123", "role": "user", "plan": "premium"}
        )
    )
    
    user = await client.get_current_user(token)
    
    assert route.called
    assert user.id == "user_123"
    assert user.role == "user"
    assert user.plan == "premium"
    assert user.username == "user"

@respx.mock
async def test_get_current_user_invalid_token():
    client = AuthClient()
    
    respx.post(f"{client.base_url}/internal/auth/verify-token").mock(
        return_value=Response(status_code=401)
    )
    
    with pytest.raises(HTTPException) as exc_info:
        await client.get_current_user("invalid_token")
        
    assert exc_info.value.status_code == 401
    assert "Invalid token or unauthorized" in exc_info.value.detail

@respx.mock
async def test_get_user_quota_success():
    client = AuthClient()
    user_id = "user_123"
    
    respx.get(f"{client.base_url}/internal/users/{user_id}/quota").mock(
        return_value=Response(
            status_code=200,
            json={
                "user_id": user_id,
                "plan": "premium",
                "limits": {"max_watches": 10, "check_interval_seconds": 30}
            }
        )
    )
    
    quota = await client.get_user_quota(user_id)
    
    assert isinstance(quota, UserQuotaResponse)
    assert quota.max_watches == 10
    assert quota.check_interval_seconds == 30

@respx.mock
async def test_auth_service_connection_error():
    client = AuthClient()
    
    respx.get(f"{client.base_url}/internal/users/123/quota").mock(
        side_effect=RequestError("Connection refused")
    )
    
    with pytest.raises(HTTPException) as exc_info:
        await client.get_user_quota("123")
        
    assert exc_info.value.status_code == 503
    assert "Auth service connection error" in exc_info.value.detail