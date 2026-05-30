# tests/test_checkout.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestCheckout:
    @patch("app.deps.httpx.AsyncClient.get")
    @patch("app.services.subscription_service.create_checkout_session")
    def test_create_checkout_new_customer(self, mock_create_session, mock_auth_get, mock_auth_header):
        mock_auth_get.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 1, "email": "test@example.com"}
        )
        mock_create_session.return_value = {
            "checkout_url": "https://checkout.stripe.com/test",
            "session_id": "sess_test",
            "customer_id": "cus_test",
        }

        resp = client.post(
            "/billing/checkout", json={"plan": "pro"}, headers=mock_auth_header
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "sess_test"
        assert "checkout_url" in data

    @patch("app.deps.httpx.AsyncClient.get")
    @patch("app.services.subscription_service.create_checkout_session")
    def test_create_checkout_existing_customer(self, mock_create_session, mock_auth_get, mock_auth_header):
        mock_auth_get.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 1, "email": "test@example.com"}
        )
        mock_create_session.return_value = {
            "checkout_url": "https://checkout.stripe.com/test2",
            "session_id": "sess_test2",
            "customer_id": "cus_existing",
        }

        resp = client.post(
            "/billing/checkout", json={"plan": "business"}, headers=mock_auth_header
        )

        assert resp.status_code == 200
        assert resp.json()["session_id"] == "sess_test2"

    @patch("app.deps.httpx.AsyncClient.get")
    @patch("app.services.subscription_service.create_checkout_session")
    def test_create_checkout_invalid_plan(self, mock_create_session, mock_auth_get, mock_auth_header):
        mock_auth_get.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 1, "email": "test@example.com"}
        )
        mock_create_session.side_effect = ValueError("Invalid plan")

        resp = client.post(
            "/billing/checkout", json={"plan": "enterprise"}, headers=mock_auth_header
        )

        assert resp.status_code == 422
