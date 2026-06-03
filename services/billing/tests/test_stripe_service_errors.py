# tests/test_stripe_service_errors.py
import pytest
from unittest.mock import patch, MagicMock
from app.services import stripe_service


class TestStripeErrorHandling:
    @patch("app.services.stripe_service.asyncio.to_thread")
    async def test_card_error(self, mock_to_thread):
        mock_err = MagicMock()
        mock_err.user_message = "Card declined"
        mock_err.code = "card_declined"
        mock_to_thread.side_effect = stripe_service.stripe.error.CardError(
            "Card declined", "param", "card_declined"
        )

        with pytest.raises(stripe_service.CardError, match="Card declined"):
            await stripe_service.create_customer("test@example.com")

    @patch("app.services.stripe_service.asyncio.to_thread")
    async def test_rate_limit_error(self, mock_to_thread):
        mock_to_thread.side_effect = stripe_service.stripe.error.RateLimitError("Rate limit")

        with pytest.raises(stripe_service.RateLimitError, match="Too many requests"):
            await stripe_service.create_customer("test@example.com")

    @patch("app.services.stripe_service.asyncio.to_thread")
    async def test_authentication_error(self, mock_to_thread):
        mock_to_thread.side_effect = stripe_service.stripe.error.AuthenticationError("Auth failed")

        with pytest.raises(stripe_service.AuthenticationError, match="Stripe authentication failed"):
            await stripe_service.create_customer("test@example.com")

    @patch("app.services.stripe_service.asyncio.to_thread")
    async def test_invalid_request_error(self, mock_to_thread):
        mock_to_thread.side_effect = stripe_service.stripe.error.InvalidRequestError("Bad request", "param")

        with pytest.raises(stripe_service.InvalidRequestError, match="Bad request"):
            await stripe_service.create_customer("test@example.com")

    @patch("app.services.stripe_service.asyncio.to_thread")
    async def test_generic_stripe_error(self, mock_to_thread):
        mock_to_thread.side_effect = stripe_service.stripe.error.StripeError("Something went wrong")

        with pytest.raises(stripe_service.StripeError, match="Something went wrong"):
            await stripe_service.create_customer("test@example.com")

    @patch("app.services.stripe_service.asyncio.to_thread")
    async def test_create_portal_session(self, mock_to_thread):
        mock_session = MagicMock()
        mock_session.id = "portal_123"
        mock_session.url = "https://billing.stripe.com/portal/test"
        mock_to_thread.return_value = mock_session

        result = await stripe_service.create_portal_session("cus_123")
        assert result.id == "portal_123"

    @patch("app.services.stripe_service.asyncio.to_thread")
    async def test_cancel_subscription(self, mock_to_thread):
        mock_sub = MagicMock()
        mock_sub.status = "active"
        mock_to_thread.return_value = mock_sub

        result = await stripe_service.cancel_subscription("sub_123")
        assert result.status == "active"

    @patch("app.services.stripe_service.asyncio.to_thread")
    async def test_list_invoices(self, mock_to_thread):
        mock_invoice = MagicMock()
        mock_invoice.id = "inv_1"
        mock_list = MagicMock()
        mock_list.data = [mock_invoice]
        mock_to_thread.return_value = mock_list

        result = await stripe_service.list_invoices("cus_123")
        assert len(result) == 1
        assert result[0].id == "inv_1"

    @patch("app.services.stripe_service.asyncio.to_thread")
    async def test_get_subscription(self, mock_to_thread):
        mock_sub = MagicMock()
        mock_sub.id = "sub_123"
        mock_to_thread.return_value = mock_sub

        result = await stripe_service.get_subscription("sub_123")
        assert result.id == "sub_123"
