# tests/test_webhook.py
import uuid
import pytest
import stripe
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy import select

from app.main import app
from app.models import Customer, Subscription, Invoice, WebhookEvent, PlanEnum, StatusEnum, InvoiceStatus
from app.services import webhook_service
from app.models.base import utc_now
from app.config import settings


class FakeStripeEvent:
    """Fake Stripe event that mimics stripe.Event interface."""
    def __init__(self, event_id, event_type, data_object):
        self._data = {"id": event_id, "type": event_type, "data": {"object": data_object}}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def to_dict(self):
        return self._data


def make_stripe_subscription_dict(
    sub_id="sub_test_123",
    status="active",
    customer="cus_test_123",
    price_id=None,
    current_period_start=1700000000,
    current_period_end=1702600000,
    cancel_at_period_end=False,
):
    price_id = price_id or settings.STRIPE_PRO_PRICE_ID
    return {
        "id": sub_id,
        "status": status,
        "customer": customer,
        "items": {"data": [{"price": {"id": price_id}}]},
        "current_period_start": current_period_start,
        "current_period_end": current_period_end,
        "cancel_at_period_end": cancel_at_period_end,
    }


def make_stripe_invoice_dict(
    invoice_id="inv_test_123",
    customer="cus_test_123",
    amount_paid=2999,
    amount_due=2999,
    currency="usd",
    hosted_invoice_url="https://stripe.com/invoice.pdf",
):
    return {
        "id": invoice_id,
        "customer": customer,
        "amount_paid": amount_paid,
        "amount_due": amount_due,
        "currency": currency,
        "hosted_invoice_url": hosted_invoice_url,
    }


class TestWebhookRouter:
    @patch("app.routers.webhook.stripe.Webhook.construct_event")
    def test_invalid_signature(self, mock_construct, client):
        mock_construct.side_effect = stripe.error.SignatureVerificationError(
            "Invalid signature", "sig"
        )
        resp = client.post("/webhooks/stripe", data=b"{}", headers={"stripe-signature": "bad_sig"})
        assert resp.status_code == 400
        assert "Invalid signature" in resp.json()["detail"]

    def test_missing_signature(self, client):
        resp = client.post("/webhooks/stripe", data=b"{}")
        assert resp.status_code == 400
        assert "Missing Stripe-Signature header" in resp.json()["detail"]

    @patch("app.routers.webhook.stripe.Webhook.construct_event")
    @patch("app.routers.webhook.webhook_service.process_webhook_event")
    async def test_idempotency(self, mock_process, mock_construct, client, db_session):
        event_id = "evt_dup_123"
        # Pre-record the event
        db_session.add(WebhookEvent(
            stripe_event_id=event_id,
            event_type="checkout.session.completed",
            payload={"id": event_id},
            processed_at=utc_now(),
        ))
        await db_session.commit()

        mock_construct.return_value = FakeStripeEvent(
            event_id, "checkout.session.completed", {}
        )

        resp = client.post("/webhooks/stripe", data=b"{}", headers={"stripe-signature": "valid_sig"})
        assert resp.status_code == 200
        mock_process.assert_not_called()

    @patch("app.routers.webhook.stripe.Webhook.construct_event")
    @patch("app.routers.webhook.webhook_service.process_webhook_event")
    def test_checkout_completed_queued(self, mock_process, mock_construct, client):
        event_id = "evt_checkout_123"
        mock_construct.return_value = FakeStripeEvent(
            event_id,
            "checkout.session.completed",
            {"customer": "cus_test", "subscription": "sub_test"},
        )

        resp = client.post("/webhooks/stripe", data=b"{}", headers={"stripe-signature": "valid_sig"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "received"
        mock_process.assert_called_once()

    @patch("app.routers.webhook.stripe.Webhook.construct_event")
    @patch("app.routers.webhook.webhook_service.process_webhook_event")
    def test_unhandled_event_queued(self, mock_process, mock_construct, client):
        event_id = "evt_other_123"
        mock_construct.return_value = FakeStripeEvent(
            event_id, "charge.succeeded", {}
        )

        resp = client.post("/webhooks/stripe", data=b"{}", headers={"stripe-signature": "valid_sig"})
        assert resp.status_code == 200
        mock_process.assert_called_once()


class TestWebhookService:
    async def _create_customer(self, db_session, user_id=None, stripe_customer_id=None):
        user_id = user_id or uuid.uuid4()
        customer = Customer(
            user_id=user_id,
            stripe_customer_id=stripe_customer_id or f"cus_{uuid.uuid4().hex[:12]}",
            email="test@example.com",
        )
        db_session.add(customer)
        await db_session.commit()
        return customer

    async def _create_subscription(self, db_session, customer, sub_id=None, plan=PlanEnum.pro, status=StatusEnum.active):
        sub = Subscription(
            user_id=customer.user_id,
            stripe_subscription_id=sub_id or f"sub_{uuid.uuid4().hex[:12]}",
            plan=plan,
            status=status,
            current_period_start=utc_now(),
            current_period_end=utc_now(),
            cancel_at_period_end=False,
        )
        db_session.add(sub)
        await db_session.commit()
        return sub

    @patch("app.services.webhook_service.get_publisher")
    async def test_process_webhook_idempotency(self, mock_get_publisher, db_session):
        event_id = "evt_idem_123"
        db_session.add(WebhookEvent(
            stripe_event_id=event_id,
            event_type="checkout.session.completed",
            payload={"id": event_id},
            processed_at=utc_now(),
        ))
        await db_session.commit()

        mock_publisher = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        await webhook_service.process_webhook_event(
            {"id": event_id, "type": "checkout.session.completed", "data": {"object": {}}}
        )

        mock_publisher.publish.assert_not_called()

    @patch("app.services.webhook_service.get_publisher")
    @patch("app.services.webhook_service.stripe_service.get_subscription")
    async def test_checkout_session_completed(self, mock_get_sub, mock_get_publisher, db_session):
        customer = await self._create_customer(db_session)

        mock_sub = MagicMock()
        mock_sub.id = "sub_checkout_123"
        mock_sub.status = "active"
        mock_sub.current_period_start = 1700000000
        mock_sub.current_period_end = 1702600000
        mock_sub.cancel_at_period_end = False
        mock_sub.items.data = [MagicMock(price=MagicMock(id=settings.STRIPE_PRO_PRICE_ID))]
        mock_get_sub.return_value = mock_sub

        mock_publisher = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        event = {
            "id": "evt_checkout_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": customer.stripe_customer_id,
                    "subscription": "sub_checkout_123",
                }
            },
        }
        await webhook_service.process_webhook_event(event)

        # Verify subscription created
        result = await db_session.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == "sub_checkout_123")
        )
        sub = result.scalar_one()
        assert sub.plan == PlanEnum.pro
        assert sub.status == StatusEnum.active
        assert sub.user_id == customer.user_id

        # Verify event published
        mock_publisher.publish.assert_called_once_with("subscription.changed", {
            "user_id": str(customer.user_id),
            "plan": "pro",
            "status": "active",
            "stripe_subscription_id": "sub_checkout_123",
        })

    @patch("app.services.webhook_service.get_publisher")
    async def test_customer_subscription_updated(self, mock_get_publisher, db_session):
        customer = await self._create_customer(db_session)
        sub = await self._create_subscription(db_session, customer, sub_id="sub_updated_123", plan=PlanEnum.pro)

        mock_publisher = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        event = {
            "id": "evt_updated_1",
            "type": "customer.subscription.updated",
            "data": {
                "object": make_stripe_subscription_dict(
                    sub_id="sub_updated_123",
                    status="past_due",
                    price_id=settings.STRIPE_BUSINESS_PRICE_ID,
                )
            },
        }
        await webhook_service.process_webhook_event(event)

        await db_session.refresh(sub)
        assert sub.status == StatusEnum.past_due
        assert sub.plan == PlanEnum.business

        mock_publisher.publish.assert_called_once_with("subscription.changed", {
            "user_id": str(customer.user_id),
            "plan": "business",
            "status": "past_due",
            "cancel_at_period_end": False,
            "stripe_subscription_id": "sub_updated_123",
        })

    @patch("app.services.webhook_service.get_publisher")
    async def test_customer_subscription_deleted(self, mock_get_publisher, db_session):
        customer = await self._create_customer(db_session)
        sub = await self._create_subscription(db_session, customer, sub_id="sub_deleted_123", plan=PlanEnum.pro)

        mock_publisher = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        event = {
            "id": "evt_deleted_1",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {"id": "sub_deleted_123", "customer": customer.stripe_customer_id}
            },
        }
        await webhook_service.process_webhook_event(event)

        await db_session.refresh(sub)
        assert sub.status == StatusEnum.canceled
        assert sub.plan == PlanEnum.free

        mock_publisher.publish.assert_called_once_with("subscription.changed", {
            "user_id": str(customer.user_id),
            "plan": "free",
            "status": "canceled",
            "stripe_subscription_id": "sub_deleted_123",
        })

    @patch("app.services.webhook_service.get_publisher")
    async def test_invoice_paid(self, mock_get_publisher, db_session):
        customer = await self._create_customer(db_session)

        mock_publisher = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        event = {
            "id": "evt_invoice_1",
            "type": "invoice.paid",
            "data": {
                "object": make_stripe_invoice_dict(invoice_id="inv_paid_123", customer=customer.stripe_customer_id)
            },
        }
        await webhook_service.process_webhook_event(event)

        result = await db_session.execute(
            select(Invoice).where(Invoice.stripe_invoice_id == "inv_paid_123")
        )
        inv = result.scalar_one()
        assert inv.user_id == customer.user_id
        assert inv.status == InvoiceStatus.paid
        assert inv.amount_cents == 2999

        mock_publisher.publish.assert_called_once_with("invoice.paid", {
            "user_id": str(customer.user_id),
            "invoice_id": "inv_paid_123",
            "amount_paid": 2999,
            "currency": "usd",
        })

    @patch("app.services.webhook_service.get_publisher")
    async def test_invoice_paid_idempotency(self, mock_get_publisher, db_session):
        customer = await self._create_customer(db_session)
        db_session.add(Invoice(
            user_id=customer.user_id,
            stripe_invoice_id="inv_idem_123",
            amount_cents=2999,
            currency="usd",
            status=InvoiceStatus.paid,
        ))
        await db_session.commit()

        mock_publisher = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        event = {
            "id": "evt_invoice_2",
            "type": "invoice.paid",
            "data": {
                "object": make_stripe_invoice_dict(invoice_id="inv_idem_123", customer=customer.stripe_customer_id)
            },
        }
        await webhook_service.process_webhook_event(event)

        # Should not publish because invoice already exists
        mock_publisher.publish.assert_not_called()

    @patch("app.services.webhook_service.get_publisher")
    async def test_payment_failed(self, mock_get_publisher, db_session):
        customer = await self._create_customer(db_session)

        mock_publisher = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        event = {
            "id": "evt_pay_fail_1",
            "type": "invoice.payment_failed",
            "data": {
                "object": make_stripe_invoice_dict(invoice_id="inv_fail_123", customer=customer.stripe_customer_id)
            },
        }
        await webhook_service.process_webhook_event(event)

        mock_publisher.publish.assert_called_once_with("payment.failed", {
            "user_id": str(customer.user_id),
            "invoice_id": "inv_fail_123",
            "amount_due": 2999,
            "currency": "usd",
        })

    @patch("app.services.webhook_service.get_publisher")
    async def test_unhandled_event(self, mock_get_publisher, db_session):
        mock_publisher = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        event = {
            "id": "evt_unhandled_1",
            "type": "charge.succeeded",
            "data": {"object": {}},
        }
        await webhook_service.process_webhook_event(event)

        # Webhook event should still be recorded
        result = await db_session.execute(
            select(WebhookEvent).where(WebhookEvent.stripe_event_id == "evt_unhandled_1")
        )
        assert result.scalar_one() is not None
        mock_publisher.publish.assert_not_called()

    @patch("app.services.webhook_service.get_publisher")
    async def test_invalid_payload_value_error(self, mock_get_publisher, db_session):
        """Test that ValueError from construct_event is handled gracefully in service processing."""
        # This test verifies the service layer doesn't crash on bad data
        mock_publisher = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        event = {
            "id": "evt_bad_1",
            "type": "checkout.session.completed",
            "data": {"object": {}},  # missing customer/subscription
        }
        # Should not raise
        await webhook_service.process_webhook_event(event)
        # No subscription created, but webhook event recorded
        result = await db_session.execute(
            select(WebhookEvent).where(WebhookEvent.stripe_event_id == "evt_bad_1")
        )
        assert result.scalar_one() is not None
