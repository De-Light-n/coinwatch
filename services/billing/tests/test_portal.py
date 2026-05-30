# tests/test_portal.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestPortal:
    @patch("app.deps.httpx.AsyncClient.get")
    @patch("app.services.subscription_service.create_portal_session")
    def test_create_portal(self, mock_portal, mock_auth_get, mock_auth_header):
        mock_auth_get.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 1}
        )
        mock_portal.return_value = {
            "portal_url": "https://billing.stripe.com/portal/test"
        }

        resp = client.post("/billing/portal", headers=mock_auth_header)

        assert resp.status_code == 200
        assert "portal_url" in resp.json()

    @patch("app.deps.httpx.AsyncClient.get")
    @patch("app.services.subscription_service.create_portal_session")
    def test_create_portal_no_subscription(self, mock_portal, mock_auth_get, mock_auth_header):
        mock_auth_get.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 1}
        )
        mock_portal.side_effect = ValueError("Customer not found")

        resp = client.post("/billing/portal", headers=mock_auth_header)

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Customer not found"

    @patch("app.deps.httpx.AsyncClient.get")
    @patch("app.services.subscription_service.create_portal_session")
    def test_create_portal_no_customer_id(self, mock_portal, mock_auth_get, mock_auth_header):
        mock_auth_get.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 1}
        )
        mock_portal.side_effect = ValueError("Customer not found")

        resp = client.post("/billing/portal", headers=mock_auth_header)

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Customer not found"
