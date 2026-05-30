import pytest
import respx
from httpx import Response, RequestError
from fastapi import HTTPException

from app.clients.auth import AuthClient, UserQuotaResponse

pytestmark = pytest.mark.anyio


# ─── get_current_user ────────────────────────────────────────────

@respx.mock
async def test_get_current_user_success():
    client = AuthClient()
    route = respx.post(f"{client.base_url}/internal/auth/verify-token").mock(
        return_value=Response(
            status_code=200,
            json={"user_id": "user_123", "role": "user", "plan": "premium"},
        )
    )

    user = await client.get_current_user("valid_jwt_token")

    assert route.called
    assert user.id == "user_123"
    assert user.role == "user"
    assert user.plan == "premium"


@respx.mock
async def test_get_current_user_invalid_token_401():
    client = AuthClient()
    respx.post(f"{client.base_url}/internal/auth/verify-token").mock(
        return_value=Response(status_code=401)
    )

    with pytest.raises(HTTPException) as exc:
        await client.get_current_user("invalid_token")

    assert exc.value.status_code == 401
    assert "Invalid token or unauthorized" in exc.value.detail


@respx.mock
async def test_get_current_user_forbidden_403():
    client = AuthClient()
    respx.post(f"{client.base_url}/internal/auth/verify-token").mock(
        return_value=Response(status_code=403)
    )

    with pytest.raises(HTTPException) as exc:
        await client.get_current_user("forbidden_token")

    assert exc.value.status_code == 401


@respx.mock
async def test_get_current_user_server_error_raises():
    client = AuthClient()
    respx.post(f"{client.base_url}/internal/auth/verify-token").mock(
        return_value=Response(status_code=500)
    )

    with pytest.raises(HTTPException) as exc:
        await client.get_current_user("some_token")

    assert exc.value.status_code == 401


async def test_get_current_user_empty_token_raises():
    client = AuthClient()

    with pytest.raises(HTTPException) as exc:
        await client.get_current_user("")

    assert exc.value.status_code == 401


@respx.mock
async def test_get_current_user_connection_error_raises_503():
    client = AuthClient()
    respx.post(f"{client.base_url}/internal/auth/verify-token").mock(
        side_effect=RequestError("Connection refused")
    )

    with pytest.raises(HTTPException) as exc:
        await client.get_current_user("some_token")

    assert exc.value.status_code == 503
    assert "Auth service connection error" in exc.value.detail


# ─── get_user_quota ──────────────────────────────────────────────

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
                "limits": {"max_watches": 10, "check_interval_seconds": 30},
            },
        )
    )

    quota = await client.get_user_quota(user_id)

    assert isinstance(quota, UserQuotaResponse)
    assert quota.max_watches == 10
    assert quota.check_interval_seconds == 30
    assert quota.plan == "premium"


@respx.mock
async def test_get_user_quota_free_plan_defaults():
    client = AuthClient()
    user_id = "user_456"
    respx.get(f"{client.base_url}/internal/users/{user_id}/quota").mock(
        return_value=Response(
            status_code=200,
            json={
                "user_id": user_id,
                "plan": "free",
                "limits": {},  # no explicit limits — should use defaults
            },
        )
    )

    quota = await client.get_user_quota(user_id)

    assert quota.max_watches == 5          # default
    assert quota.check_interval_seconds == 60  # default


@respx.mock
async def test_get_user_quota_not_found_404():
    client = AuthClient()
    respx.get(f"{client.base_url}/internal/users/unknown/quota").mock(
        return_value=Response(status_code=404)
    )

    with pytest.raises(HTTPException) as exc:
        await client.get_user_quota("unknown")

    assert exc.value.status_code == 404


@respx.mock
async def test_get_user_quota_server_error_500():
    client = AuthClient()
    respx.get(f"{client.base_url}/internal/users/user_1/quota").mock(
        return_value=Response(status_code=500)
    )

    with pytest.raises(HTTPException) as exc:
        await client.get_user_quota("user_1")

    assert exc.value.status_code == 500


@respx.mock
async def test_get_user_quota_connection_error_raises_503():
    client = AuthClient()
    respx.get(f"{client.base_url}/internal/users/123/quota").mock(
        side_effect=RequestError("Connection refused")
    )

    with pytest.raises(HTTPException) as exc:
        await client.get_user_quota("123")

    assert exc.value.status_code == 503
    assert "Auth service connection error" in exc.value.detail


# ─── UserQuotaResponse properties ────────────────────────────────

def test_user_quota_response_max_watches_from_limits():
    quota = UserQuotaResponse(
        user_id="u1", plan="pro",
        limits={"max_watches": 20, "check_interval_seconds": 15}
    )
    assert quota.max_watches == 20


def test_user_quota_response_interval_from_limits():
    quota = UserQuotaResponse(
        user_id="u1", plan="pro",
        limits={"max_watches": 20, "check_interval_seconds": 15}
    )
    assert quota.check_interval_seconds == 15


def test_user_quota_response_defaults_when_limits_empty():
    quota = UserQuotaResponse(user_id="u1", plan="free", limits={})
    assert quota.max_watches == 5
    assert quota.check_interval_seconds == 60