import stripe
import os
import asyncio
import structlog
from typing import Any, Dict, List
from app.config import settings

# Configure Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY

logger = structlog.get_logger()


class StripeError(Exception):
    """Base exception for Stripe errors"""
    pass


class CardError(StripeError):
    """Card declined or invalid"""
    pass


class RateLimitError(StripeError):
    """Rate limit exceeded"""
    pass


class AuthenticationError(StripeError):
    """Invalid API key"""
    pass


class InvalidRequestError(StripeError):
    """Invalid request parameters"""
    pass


async def _execute_stripe_call(func, *args, **kwargs) -> Any:
    """Execute Stripe API call with error handling"""
    try:
        return await asyncio.to_thread(func, *args, **kwargs)
    except stripe.error.CardError as e:
        logger.error("stripe_card_error", error=e.user_message, code=e.code)
        raise CardError(e.user_message)
    except stripe.error.RateLimitError as e:
        logger.error("stripe_rate_limit_error")
        raise RateLimitError("Too many requests to Stripe")
    except stripe.error.AuthenticationError as e:
        logger.error("stripe_auth_error")
        raise AuthenticationError("Stripe authentication failed")
    except stripe.error.InvalidRequestError as e:
        logger.error("stripe_invalid_request", message=str(e))
        raise InvalidRequestError(str(e))
    except stripe.error.StripeError as e:
        logger.error("stripe_api_error", message=str(e))
        raise StripeError(str(e))


async def create_customer(email: str) -> Dict[str, Any]:
    """Create a new Stripe customer"""
    logger.info("creating_stripe_customer", email=email)
    customer = await _execute_stripe_call(stripe.Customer.create, email=email)
    logger.info("stripe_customer_created", customer_id=customer.id, email=email)
    return customer


async def create_checkout_session(
    customer_id: str, 
    price_id: str, 
    success_url: str = None,
    cancel_url: str = None
) -> Dict[str, Any]:
    """Create a checkout session for subscription"""
    if success_url is None:
        success_url = settings.CHECKOUT_SUCCESS_URL or "http://localhost:3000/success?session_id={CHECKOUT_SESSION_ID}"
    if cancel_url is None:
        cancel_url = settings.CHECKOUT_CANCEL_URL or "http://localhost:3000/cancel"
    
    logger.info("creating_checkout_session", customer_id=customer_id, price_id=price_id)
    session = await _execute_stripe_call(
        stripe.checkout.Session.create,
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
    )
    logger.info("checkout_session_created", session_id=session.id)
    return session


async def create_portal_session(
    customer_id: str,
    return_url: str = None
) -> Dict[str, Any]:
    """Create a customer portal session"""
    if return_url is None:
        return_url = settings.PORTAL_RETURN_URL or "http://localhost:3000/account"
    
    logger.info("creating_portal_session", customer_id=customer_id)
    session = await _execute_stripe_call(
        stripe.billing_portal.Session.create,
        customer=customer_id,
        return_url=return_url,
    )
    logger.info("portal_session_created", session_id=session.id)
    return session


async def cancel_subscription(subscription_id: str) -> Dict[str, Any]:
    """Cancel a subscription at period end"""
    logger.info("canceling_subscription", subscription_id=subscription_id)
    subscription = await _execute_stripe_call(
        stripe.Subscription.modify,
        subscription_id,
        cancel_at_period_end=True,
    )
    logger.info("subscription_canceled", subscription_id=subscription_id, status=subscription.status)
    return subscription


async def list_invoices(customer_id: str, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
    """List customer invoices with pagination"""
    logger.info("fetching_invoices", customer_id=customer_id, limit=limit, offset=offset)
    invoices = await _execute_stripe_call(
        stripe.Invoice.list,
        customer=customer_id,
        limit=limit + 1,  # Fetch one extra to detect if there are more
        starting_after_id=None if offset == 0 else None,
    )
    logger.info("invoices_fetched", count=len(invoices.data))
    return invoices.data


async def get_subscription(subscription_id: str) -> Dict[str, Any]:
    """Retrieve a subscription by ID"""
    logger.info("fetching_subscription", subscription_id=subscription_id)
    subscription = await _execute_stripe_call(stripe.Subscription.retrieve, subscription_id)
    return subscription
