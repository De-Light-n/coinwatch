# tests/test_deps.py
import uuid
import jwt
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from app.deps import get_current_user


def _make_token(payload: dict, secret: str = "test-secret") -> str:
    return jwt.encode(payload, secret, algorithm="HS256")


class TestGetCurrentUser:
    async def test_missing_sub_raises_401(self):
        token = _make_token({"email": "test@example.com"})
        creds = MagicMock(credentials=token)
        db = AsyncMock()

        with pytest.raises(HTTPException) as exc:
            await get_current_user(creds, db)
        assert exc.value.status_code == 401

    async def test_missing_email_raises_401(self):
        token = _make_token({"sub": str(uuid.uuid4())})
        creds = MagicMock(credentials=token)
        db = AsyncMock()

        with pytest.raises(HTTPException) as exc:
            await get_current_user(creds, db)
        assert exc.value.status_code == 401

    async def test_invalid_sub_format_raises_401(self):
        token = _make_token({"sub": "not-a-uuid", "email": "test@example.com"})
        creds = MagicMock(credentials=token)
        db = AsyncMock()

        with pytest.raises(HTTPException) as exc:
            await get_current_user(creds, db)
        assert exc.value.status_code == 401

    async def test_invalid_token_raises_401(self):
        creds = MagicMock(credentials="bad-token")
        db = AsyncMock()

        with pytest.raises(HTTPException) as exc:
            await get_current_user(creds, db)
        assert exc.value.status_code == 401

    async def test_valid_token_returns_user(self):
        user_id = uuid.uuid4()
        token = _make_token({"sub": str(user_id), "email": "test@example.com"})
        creds = MagicMock(credentials=token)
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        user = await get_current_user(creds, db)
        assert user.id == user_id
        assert user.email == "test@example.com"

    async def test_valid_token_with_customer(self):
        user_id = uuid.uuid4()
        token = _make_token({"sub": str(user_id), "email": "test@example.com"})
        creds = MagicMock(credentials=token)
        db = AsyncMock()
        customer = MagicMock(stripe_customer_id="cus_123")
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=customer))

        user = await get_current_user(creds, db)
        assert user.stripe_customer_id == "cus_123"
