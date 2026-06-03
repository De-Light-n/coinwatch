# tests/test_invoices.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestInvoices:
    @patch("app.deps.httpx.AsyncClient.get")
    @patch("app.services.subscription_service.get_user_invoices")
    def test_list_invoices(self, mock_get_invoices, mock_auth_get, mock_auth_header):
        mock_auth_get.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 1}
        )
        mock_get_invoices.return_value = {
            "invoices": [
                {
                    "id": "inv_test",
                    "number": "INV-001",
                    "amount_paid": 2999,
                    "currency": "usd",
                    "status": "paid",
                    "created": 1700000000,
                    "pdf_url": "https://stripe.com/invoice.pdf",
                }
            ],
            "total": 1,
            "limit": 10,
            "offset": 0,
        }

        resp = client.get(
            "/billing/invoices?page=1&page_size=20", headers=mock_auth_header
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["invoices"]) == 1
        assert data["invoices"][0]["id"] == "inv_test"

    @patch("app.deps.httpx.AsyncClient.get")
    @patch("app.services.subscription_service.get_user_invoices")
    def test_list_invoices_pagination(self, mock_get_invoices, mock_auth_get, mock_auth_header):
        mock_auth_get.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 1}
        )
        mock_get_invoices.return_value = {
            "invoices": [],
            "total": 0,
            "limit": 10,
            "offset": 0,
        }

        resp = client.get(
            "/billing/invoices?page=2&page_size=10", headers=mock_auth_header
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 10
        assert data["offset"] == 0

    @patch("app.deps.httpx.AsyncClient.get")
    @patch("app.services.subscription_service.get_user_invoices")
    def test_list_invoices_empty(self, mock_get_invoices, mock_auth_get, mock_auth_header):
        mock_auth_get.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 1}
        )
        mock_get_invoices.return_value = {
            "invoices": [],
            "total": 0,
            "limit": 10,
            "offset": 0,
        }

        resp = client.get("/billing/invoices", headers=mock_auth_header)

        assert resp.status_code == 200
        assert resp.json()["invoices"] == []
