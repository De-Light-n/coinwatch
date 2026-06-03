# tests/test_cancel.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestCancel:
    @patch("app.deps.httpx.AsyncClient.get")
    @patch("app.services.subscription_service.cancel_subscription_at_period_end")
    def test_cancel_subscription(self, mock_cancel, mock_auth_get, mock_auth_header):
        mock_auth_get.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 1}
        )
        mock_cancel.return_value = {
            "status": "canceled",
            "subscription_id": "sub_test",
            "cancel_at_period_end": True,
        }

        resp = client.post("/billing/cancel", headers=mock_auth_header)

        assert resp.status_code == 200
        assert resp.json()["cancel_at_period_end"] is True
        mock_cancel.assert_called_once()

    @patch("app.deps.httpx.AsyncClient.get")
    @patch("app.services.subscription_service.cancel_subscription_at_period_end")
    def test_cancel_no_subscription(self, mock_cancel, mock_auth_get, mock_auth_header):
        mock_auth_get.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 1}
        )
        mock_cancel.side_effect = ValueError("No active subscription found")

        resp = client.post("/billing/cancel", headers=mock_auth_header)

        assert resp.status_code == 400
        assert resp.json()["detail"] == "No active subscription found"

    @patch("app.deps.httpx.AsyncClient.get")
    @patch("app.services.subscription_service.cancel_subscription_at_period_end")
    def test_cancel_no_stripe_subscription(self, mock_cancel, mock_auth_get, mock_auth_header):
        mock_auth_get.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 1}
        )
        mock_cancel.side_effect = ValueError("No active subscription found")

        resp = client.post("/billing/cancel", headers=mock_auth_header)

        assert resp.status_code == 400
        assert resp.json()["detail"] == "No active subscription found"
