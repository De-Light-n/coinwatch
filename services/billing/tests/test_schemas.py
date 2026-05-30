# tests/test_schemas.py
import pytest
from pydantic import ValidationError

from app.models.schemas.billing import (
    CheckoutRequest, CheckoutResponse, PortalResponse,
    CancelResponse, SubscriptionResponse, InvoicesResponse,
    InvoiceItemResponse, ErrorResponse
)
from app.models.schemas.customer import CustomerCreate, CustomerOut
from app.models.schemas.invoice import InvoiceCreate, InvoiceOut
from app.models.schemas.subscription import SubscriptionCreate, SubscriptionOut


class TestCheckoutRequest:
    def test_valid_pro(self):
        req = CheckoutRequest(plan="pro")
        assert req.plan == "pro"

    def test_valid_business(self):
        req = CheckoutRequest(plan="business")
        assert req.plan == "business"

    def test_invalid_plan_raises(self):
        with pytest.raises(ValidationError):
            CheckoutRequest(plan="enterprise")


class TestCheckoutResponse:
    def test_fields(self):
        resp = CheckoutResponse(checkout_url="https://stripe.com", session_id="sess_123")
        assert resp.session_id == "sess_123"


class TestPortalResponse:
    def test_fields(self):
        resp = PortalResponse(portal_url="https://billing.stripe.com")
        assert resp.portal_url == "https://billing.stripe.com"


class TestCancelResponse:
    def test_fields(self):
        resp = CancelResponse(status="canceled", subscription_id="sub_123", cancel_at_period_end=True)
        assert resp.cancel_at_period_end is True


class TestSubscriptionResponse:
    def test_with_subscription(self):
        resp = SubscriptionResponse(plan="pro", status="active", cancel_at_period_end=False)
        assert resp.plan == "pro"

    def test_free_plan(self):
        resp = SubscriptionResponse(plan="free", status="active", cancel_at_period_end=False)
        assert resp.id is None


class TestInvoiceItemResponse:
    def test_fields(self):
        resp = InvoiceItemResponse(
            id="inv_1", number="INV-001", amount_paid=2999,
            currency="usd", status="paid", created=1700000000
        )
        assert resp.amount_paid == 2999


class TestInvoicesResponse:
    def test_empty(self):
        resp = InvoicesResponse(invoices=[], total=0, limit=10, offset=0)
        assert resp.total == 0

    def test_with_items(self):
        item = InvoiceItemResponse(
            id="inv_1", number="INV-001", amount_paid=2999,
            currency="usd", status="paid", created=1700000000
        )
        resp = InvoicesResponse(invoices=[item], total=1, limit=10, offset=0)
        assert resp.total == 1


class TestErrorResponse:
    def test_fields(self):
        resp = ErrorResponse(detail="Something went wrong", code="ERR_001")
        assert resp.detail == "Something went wrong"


class TestCustomerSchemas:
    def test_customer_create(self):
        c = CustomerCreate(user_id="123e4567-e89b-12d3-a456-426614174000", stripe_customer_id="cus_123", email="test@example.com")
        assert c.email == "test@example.com"

    def test_customer_out(self):
        c = CustomerOut(id="123e4567-e89b-12d3-a456-426614174000", stripe_customer_id="cus_123", email="test@example.com")
        assert c.id is not None


class TestInvoiceSchemas:
    def test_invoice_create(self):
        inv = InvoiceCreate(
            user_id="123e4567-e89b-12d3-a456-426614174000",
            stripe_invoice_id="inv_1",
            amount_cents=2999,
            status="paid"
        )
        assert inv.amount_cents == 2999

    def test_invoice_out(self):
        from datetime import datetime
        inv = InvoiceOut(
            id="123e4567-e89b-12d3-a456-426614174000",
            user_id="123e4567-e89b-12d3-a456-426614174000",
            stripe_invoice_id="inv_1",
            amount_cents=2999,
            currency="usd",
            status="paid",
            created_at=datetime.utcnow()
        )
        assert inv.status == "paid"


class TestSubscriptionSchemas:
    def test_subscription_create(self):
        from datetime import datetime
        sub = SubscriptionCreate(
            user_id="123e4567-e89b-12d3-a456-426614174000",
            stripe_subscription_id="sub_1",
            plan="pro",
            status="active",
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow(),
        )
        assert sub.plan == "pro"

    def test_subscription_out(self):
        from datetime import datetime
        sub = SubscriptionOut(
            id="123e4567-e89b-12d3-a456-426614174000",
            user_id="123e4567-e89b-12d3-a456-426614174000",
            stripe_subscription_id="sub_1",
            plan="pro",
            status="active",
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow(),
            cancel_at_period_end=False,
        )
        assert sub.plan == "pro"
