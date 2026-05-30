import sys
import os
import uuid
import jwt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ.setdefault("BILLING_DB_URL", "sqlite+aiosqlite:///./billing_test.db")
os.environ.setdefault("BILLING_STRIPE_SECRET_KEY", "sk_test_dummy")
os.environ.setdefault("BILLING_STRIPE_WEBHOOK_SECRET", "whsec_dummy")
os.environ.setdefault("BILLING_STRIPE_PRO_PRICE_ID", "price_dummy_pro")
os.environ.setdefault("BILLING_STRIPE_BUSINESS_PRICE_ID", "price_dummy_bus")
os.environ.setdefault("BILLING_RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
os.environ.setdefault("BILLING_AUTH_SERVICE_URL", "http://localhost:8000")
os.environ.setdefault("BILLING_SERVICE_TOKEN", "dummy_token")

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.models.base import Base
from app.db import get_db
from app.config import settings

TEST_DATABASE_URL = os.getenv("BILLING_TEST_DB_URL", "sqlite+aiosqlite:///./billing_test.db")

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


@pytest.fixture
def client():
    def override_get_db():
        async def _get_db():
            async with async_session() as session:
                yield session
        return _get_db()
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_auth_header():
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "email": "test@example.com"},
        "test-secret",
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_stripe_customer():
    return {"id": "cus_test_123", "email": "test@example.com"}


@pytest.fixture
def mock_stripe_session():
    return {"id": "sess_test_123", "url": "https://checkout.stripe.com/test", "customer": "cus_test_123"}


@pytest.fixture
def mock_stripe_subscription():
    return {
        "id": "sub_test_123",
        "status": "active",
        "customer": "cus_test_123",
        "items": {"data": [{"price": {"id": settings.STRIPE_PRO_PRICE_ID}}]},
        "current_period_start": 1700000000,
        "current_period_end": 1702600000,
        "cancel_at_period_end": False,
    }


@pytest.fixture
def mock_stripe_invoice():
    return {
        "id": "inv_test_123",
        "customer": "cus_test_123",
        "subscription": "sub_test_123",
        "amount_due": 2999,
        "amount_paid": 2999,
        "currency": "usd",
        "status": "paid",
        "invoice_pdf": "https://stripe.com/invoice.pdf",
    }


@pytest.fixture
def mock_event_publisher():
    publisher = AsyncMock()
    publisher.publish = AsyncMock(return_value=None)
    return publisher
