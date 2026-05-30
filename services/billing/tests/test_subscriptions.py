# tests/test_subscriptions.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestSubscriptions:
    @patch("app.deps.httpx.AsyncClient.get")
    @patch("app.services.subscription_service.get_user_subscriptions")
    def test_get_subscription_active(self, mock_get_subs, mock_auth_get, mock_auth_header):
        mock_auth_get.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 1}
        )
        mock_get_subs.return_value = {
            "id": "sub_test",
            "plan": "pro",
            "status": "active",
            "current_period_end": "2025-01-01T00:00:00",
            "cancel_at_period_end": False,
            "current_period_start": "2024-12-01T00:00:00",
            "created_at": "2024-12-01T00:00:00",
        }

        resp = client.get("/billing/subscriptions/me", headers=mock_auth_header)

        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "pro"
        assert data["status"] == "active"

    @patch("app.deps.httpx.AsyncClient.get")
    @patch("app.services.subscription_service.get_user_subscriptions")
    def test_get_subscription_free(self, mock_get_subs, mock_auth_get, mock_auth_header):
        mock_auth_get.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 1}
        )
        mock_get_subs.return_value = {
            "plan": "free",
            "status": "active",
            "current_period_end": None,
            "cancel_at_period_end": False,
        }

        resp = client.get("/billing/subscriptions/me", headers=mock_auth_header)

        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "free"

    def test_get_subscription_unauthorized(self):
        resp = client.get("/billing/subscriptions/me")
        assert resp.status_code == 401
