# tests/test_billing_errors.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _auth_header():
    import jwt
    import uuid
    token = jwt.encode({"sub": str(uuid.uuid4()), "email": "test@example.com"}, "test-secret", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


class TestCheckoutErrors:
    @patch("app.services.subscription_service.create_checkout_session")
    def test_card_error_returns_402(self, mock_create):
        from app.services import stripe_service
        mock_create.side_effect = stripe_service.CardError("Declined")

        resp = client.post("/billing/checkout", json={"plan": "pro"}, headers=_auth_header())
        assert resp.status_code == 402

    @patch("app.services.subscription_service.create_checkout_session")
    def test_rate_limit_returns_429(self, mock_create):
        from app.services import stripe_service
        mock_create.side_effect = stripe_service.RateLimitError("Too many")

        resp = client.post("/billing/checkout", json={"plan": "pro"}, headers=_auth_header())
        assert resp.status_code == 429

    @patch("app.services.subscription_service.create_checkout_session")
    def test_stripe_error_returns_502(self, mock_create):
        from app.services import stripe_service
        mock_create.side_effect = stripe_service.StripeError("Stripe down")

        resp = client.post("/billing/checkout", json={"plan": "pro"}, headers=_auth_header())
        assert resp.status_code == 502

    @patch("app.services.subscription_service.create_checkout_session")
    def test_unexpected_error_returns_500(self, mock_create):
        mock_create.side_effect = RuntimeError("Boom")

        resp = client.post("/billing/checkout", json={"plan": "pro"}, headers=_auth_header())
        assert resp.status_code == 500


class TestPortalErrors:
    @patch("app.services.subscription_service.create_portal_session")
    def test_stripe_error_returns_502(self, mock_portal):
        from app.services import stripe_service
        mock_portal.side_effect = stripe_service.StripeError("Stripe down")

        resp = client.post("/billing/portal", headers=_auth_header())
        assert resp.status_code == 502


class TestCancelErrors:
    @patch("app.services.subscription_service.cancel_subscription_at_period_end")
    def test_stripe_error_returns_502(self, mock_cancel):
        from app.services import stripe_service
        mock_cancel.side_effect = stripe_service.StripeError("Stripe down")

        resp = client.post("/billing/cancel", headers=_auth_header())
        assert resp.status_code == 502


class TestInvoicesErrors:
    @patch("app.services.subscription_service.get_user_invoices")
    def test_stripe_error_returns_502(self, mock_get):
        from app.services import stripe_service
        mock_get.side_effect = stripe_service.StripeError("Stripe down")

        resp = client.get("/billing/invoices", headers=_auth_header())
        assert resp.status_code == 502
