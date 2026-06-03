import pytest
from datetime import datetime, timezone
from uuid import uuid4
from app.models.schemas.billing import (
    CheckoutRequest, CheckoutResponse, PortalResponse,
    CancelResponse, SubscriptionResponse, InvoicesResponse,
    ErrorResponse
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
        with pytest.raises(ValueError):
            CheckoutRequest(plan="enterprise")

class TestCheckoutResponse:
    def test_fields(self):
        resp = CheckoutResponse(checkout_url="https://checkout.stripe.com/test", session_id="sess_test")
        assert resp.checkout_url == "https://checkout.stripe.com/test"
        assert resp.session_id == "sess_test"

class TestPortalResponse:
    def test_fields(self):
        resp = PortalResponse(portal_url="https://billing.stripe.com/portal/test")
        assert resp.portal_url == "https://billing.stripe.com/portal/test"

class TestCancelResponse:
    def test_fields(self):
        resp = CancelResponse(status="canceled", subscription_id="sub_test", cancel_at_period_end=True)
        assert resp.status == "canceled"

class TestSubscriptionResponse:
    def test_with_subscription(self):
        resp = SubscriptionResponse(
            id="123e4567-e89b-12d3-a456-426614174000",
            plan="pro",
            status="active",
            current_period_end="2024-01-01",
            cancel_at_period_end=False
        )
        assert resp.plan == "pro"

    def test_free_plan(self):
        resp = SubscriptionResponse(plan="free", status="active", current_period_end=None, cancel_at_period_end=False)
        assert resp.plan == "free"

class TestInvoicesResponse:
    def test_empty(self):
        resp = InvoicesResponse(invoices=[], total=0, limit=10, offset=0)
        assert resp.invoices == []

    def test_with_items(self):
        item = {
            "id": "inv_test",
            "number": "INV-001",
            "amount_paid": 2999,
            "currency": "usd",
            "status": "paid",
            "created": 1700000000,
            "pdf_url": "https://stripe.com/invoice.pdf"
        }
        resp = InvoicesResponse(invoices=[item], total=1, limit=10, offset=0)
        assert len(resp.invoices) == 1

class TestErrorResponse:
    def test_fields(self):
        resp = ErrorResponse(detail="Something went wrong")
        assert resp.detail == "Something went wrong"

class TestCustomerSchemas:
    def test_customer_create(self):
        c = CustomerCreate(user_id=uuid4(), stripe_customer_id="cus_test", email="test@example.com")
        assert c.email == "test@example.com"

    def test_customer_out(self):
        c = CustomerOut(
            user_id=uuid4(),
            stripe_customer_id="cus_test",
            email="test@example.com",
            created_at=datetime.now(timezone.utc)
        )
        assert c.email == "test@example.com"

class TestInvoiceSchemas:
    def test_invoice_create(self):
        inv = InvoiceCreate(
            user_id=uuid4(),
            stripe_invoice_id="inv_test",
            amount_cents=2999,
            currency="usd",
            status="paid"
        )
        assert inv.status == "paid"

    def test_invoice_out(self):
        inv = InvoiceOut(
            id=uuid4(),
            user_id=uuid4(),
            stripe_invoice_id="inv_test",
            amount_cents=2999,
            currency="usd",
            status="paid",
            created_at=datetime.now(timezone.utc)
        )
        assert inv.status == "paid"

class TestSubscriptionSchemas:
    def test_subscription_create(self):
        sub = SubscriptionCreate(
            user_id=uuid4(),
            stripe_subscription_id="sub_test",
            plan="pro",
            status="active",
            current_period_start=datetime.now(timezone.utc),
            current_period_end=datetime.now(timezone.utc)
        )
        assert sub.plan == "pro"

    def test_subscription_out(self):
        sub = SubscriptionOut(
            id=uuid4(),
            user_id=uuid4(),
            stripe_subscription_id="sub_test",
            plan="pro",
            status="active",
            current_period_start=datetime.now(timezone.utc),
            current_period_end=datetime.now(timezone.utc),
            cancel_at_period_end=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        assert sub.plan == "pro"
