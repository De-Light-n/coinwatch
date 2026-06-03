# tests/test_stripe_service.py
import pytest
from unittest.mock import patch, MagicMock
from app.services import stripe_service
from app.config import settings


class TestStripeService:
    def test_price_to_plan_mapping(self):
        PRICE_TO_PLAN = {
            settings.STRIPE_PRO_PRICE_ID: "pro",
            settings.STRIPE_BUSINESS_PRICE_ID: "business",
        }
        assert PRICE_TO_PLAN[settings.STRIPE_PRO_PRICE_ID] == "pro"

    @patch("app.services.stripe_service.stripe.Customer.create")
    async def test_create_customer(self, mock_create):
        mock_customer = MagicMock()
        mock_customer.id = "cus_test"
        mock_create.return_value = mock_customer
        result = await stripe_service.create_customer("test@example.com")
        assert result.id == "cus_test"

    @patch("app.services.stripe_service.stripe.checkout.Session.create")
    async def test_create_checkout_session(self, mock_create):
        mock_session = MagicMock()
        mock_session.id = "sess_test"
        mock_session.url = "https://checkout.stripe.com/test"
        mock_create.return_value = mock_session
        result = await stripe_service.create_checkout_session("cus_test", "price_test")
        assert result.id == "sess_test"
