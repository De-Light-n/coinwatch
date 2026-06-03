# tests/test_subscription_service.py
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import subscription_service
from app.models import Customer, Subscription, PlanEnum, StatusEnum


@pytest.fixture
def mock_db():
    return AsyncMock(spec=AsyncSession)


class TestGetOrCreateCustomer:
    @patch("app.services.subscription_service.stripe_service.create_customer")
    async def test_create_new_customer(self, mock_stripe_create, mock_db):
        user_id = uuid.uuid4()
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        mock_stripe_customer = MagicMock()
        mock_stripe_customer.id = "cus_test_123"
        mock_stripe_create.return_value = mock_stripe_customer

        result = await subscription_service.get_or_create_customer(user_id, "test@example.com", mock_db)

        assert result.user_id == user_id
        assert result.stripe_customer_id == "cus_test_123"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    async def test_get_existing_customer(self, mock_db):
        user_id = uuid.uuid4()
        existing = Customer(user_id=user_id, stripe_customer_id="cus_existing", email="test@example.com")
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=existing))

        result = await subscription_service.get_or_create_customer(user_id, "test@example.com", mock_db)

        assert result.stripe_customer_id == "cus_existing"
        mock_db.add.assert_not_called()


class TestGetActiveSubscription:
    async def test_returns_active(self, mock_db):
        user_id = uuid.uuid4()
        sub = Subscription(
            user_id=user_id,
            stripe_subscription_id="sub_123",
            plan=PlanEnum.pro,
            status=StatusEnum.active,
            current_period_start=None,
            current_period_end=None,
        )
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=sub))

        result = await subscription_service.get_active_subscription(user_id, mock_db)

        assert result.status == StatusEnum.active

    async def test_returns_none(self, mock_db):
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        result = await subscription_service.get_active_subscription(uuid.uuid4(), mock_db)

        assert result is None


class TestGetLatestSubscription:
    async def test_returns_latest(self, mock_db):
        user_id = uuid.uuid4()
        sub = Subscription(
            user_id=user_id,
            stripe_subscription_id="sub_123",
            plan=PlanEnum.pro,
            status=StatusEnum.canceled,
            current_period_start=None,
            current_period_end=None,
        )
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=sub))

        result = await subscription_service.get_latest_subscription(user_id, mock_db)

        assert result.plan == PlanEnum.pro


class TestCreateCheckoutSession:
    @patch("app.services.subscription_service.get_or_create_customer")
    @patch("app.services.subscription_service.stripe_service.create_checkout_session")
    async def test_success(self, mock_create_session, mock_get_customer, mock_db):
        user_id = uuid.uuid4()
        customer = Customer(user_id=user_id, stripe_customer_id="cus_123", email="test@example.com")
        mock_get_customer.return_value = customer

        mock_session = MagicMock()
        mock_session.id = "sess_123"
        mock_session.url = "https://checkout.stripe.com/test"
        mock_create_session.return_value = mock_session

        result = await subscription_service.create_checkout_session(user_id, "test@example.com", "pro", mock_db)

        assert result["session_id"] == "sess_123"
        assert "checkout_url" in result


class TestCreatePortalSession:
    async def test_success(self, mock_db):
        user_id = uuid.uuid4()
        customer = Customer(user_id=user_id, stripe_customer_id="cus_123", email="test@example.com")
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=customer))

        with patch("app.services.subscription_service.stripe_service.create_portal_session") as mock_portal:
            mock_session = MagicMock()
            mock_session.url = "https://billing.stripe.com/portal/test"
            mock_portal.return_value = mock_session

            result = await subscription_service.create_portal_session(user_id, mock_db)

        assert result["portal_url"] == "https://billing.stripe.com/portal/test"

    async def test_no_customer(self, mock_db):
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        with pytest.raises(ValueError, match="Customer not found"):
            await subscription_service.create_portal_session(uuid.uuid4(), mock_db)


class TestCancelSubscriptionAtPeriodEnd:
    async def test_success(self, mock_db):
        user_id = uuid.uuid4()
        sub = Subscription(
            user_id=user_id,
            stripe_subscription_id="sub_123",
            plan=PlanEnum.pro,
            status=StatusEnum.active,
            current_period_start=None,
            current_period_end=None,
        )
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=sub))

        with patch("app.services.subscription_service.stripe_service.cancel_subscription") as mock_cancel:
            mock_cancel.return_value = MagicMock(status="active")
            result = await subscription_service.cancel_subscription_at_period_end(user_id, mock_db)

        assert result["status"] == "canceled"
        assert result["cancel_at_period_end"] is True

    async def test_no_subscription(self, mock_db):
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        with pytest.raises(ValueError, match="No active subscription found"):
            await subscription_service.cancel_subscription_at_period_end(uuid.uuid4(), mock_db)


class TestGetUserSubscriptions:
    async def test_with_subscription(self, mock_db):
        user_id = uuid.uuid4()
        sub = Subscription(
            user_id=user_id,
            stripe_subscription_id="sub_123",
            plan=PlanEnum.business,
            status=StatusEnum.active,
            current_period_start=None,
            current_period_end=None,
        )
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=sub))

        result = await subscription_service.get_user_subscriptions(user_id, mock_db)

        assert result["plan"] == "business"
        assert result["status"] == "active"

    async def test_no_subscription_returns_free(self, mock_db):
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        result = await subscription_service.get_user_subscriptions(uuid.uuid4(), mock_db)

        assert result["plan"] == "free"
        assert result["status"] == "active"


class TestGetUserInvoices:
    async def test_with_customer(self, mock_db):
        user_id = uuid.uuid4()
        customer = Customer(user_id=user_id, stripe_customer_id="cus_123", email="test@example.com")
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=customer))

        with patch("app.services.subscription_service.stripe_service.list_invoices") as mock_list:
            mock_inv = MagicMock()
            mock_inv.id = "inv_1"
            mock_inv.number = "INV-001"
            mock_inv.amount_paid = 2999
            mock_inv.currency = "usd"
            mock_inv.status = "paid"
            mock_inv.created = 1700000000
            mock_inv.invoice_pdf = "https://stripe.com/invoice.pdf"
            mock_inv.hosted_invoice_url = None
            mock_list.return_value = [mock_inv]

            result = await subscription_service.get_user_invoices(user_id, mock_db)

        assert result["total"] == 1
        assert len(result["invoices"]) == 1
        assert result["invoices"][0]["id"] == "inv_1"

    async def test_no_customer_returns_empty(self, mock_db):
        mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        result = await subscription_service.get_user_invoices(uuid.uuid4(), mock_db)

        assert result["invoices"] == []
        assert result["total"] == 0
