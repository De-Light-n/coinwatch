"""Subscription service for managing subscriptions"""
import uuid
import structlog
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Customer, Subscription, PlanEnum, StatusEnum
from app.models.base import utc_now
from app.services import stripe_service

logger = structlog.get_logger()


async def get_or_create_customer(
    user_id: uuid.UUID,
    email: str,
    db: AsyncSession
) -> Customer:
    """Get existing customer or create new one"""
    # Try to get existing customer
    result = await db.execute(
        select(Customer).where(Customer.user_id == user_id)
    )
    customer = result.scalar_one_or_none()
    
    if customer:
        logger.info("customer_found", user_id=str(user_id))
        return customer
    
    # Create Stripe customer
    logger.info("creating_new_customer", user_id=str(user_id), email=email)
    stripe_customer = await stripe_service.create_customer(email)
    
    # Save to database
    customer = Customer(
        user_id=user_id,
        stripe_customer_id=stripe_customer.id,
        email=email
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    
    logger.info("customer_created", user_id=str(user_id), stripe_customer_id=stripe_customer.id)
    return customer


async def get_active_subscription(
    user_id: uuid.UUID,
    db: AsyncSession
) -> Optional[Subscription]:
    """Get user's active subscription"""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .where(Subscription.status == StatusEnum.active)
        .order_by(Subscription.created_at.desc())
    )
    return result.scalar_one_or_none()


async def get_latest_subscription(
    user_id: uuid.UUID,
    db: AsyncSession
) -> Optional[Subscription]:
    """Get user's latest subscription (active or not)"""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
    )
    return result.scalar_one_or_none()


async def create_checkout_session(
    user_id: uuid.UUID,
    email: str,
    plan: str,
    db: AsyncSession
) -> dict:
    """Create a checkout session for subscription upgrade"""
    logger.info("creating_checkout_for_user", user_id=str(user_id), plan=plan)
    
    # Get or create Stripe customer
    customer = await get_or_create_customer(user_id, email, db)
    
    # Get price ID from settings
    from app.config import settings
    price_id = (
        settings.STRIPE_PRO_PRICE_ID 
        if plan == "pro" 
        else settings.STRIPE_BUSINESS_PRICE_ID
    )
    
    # Create checkout session
    session = await stripe_service.create_checkout_session(
        customer_id=customer.stripe_customer_id,
        price_id=price_id
    )
    
    logger.info(
        "checkout_session_created_for_user",
        user_id=str(user_id),
        session_id=session.id
    )
    
    return {
        "checkout_url": session.url,
        "session_id": session.id,
        "customer_id": customer.stripe_customer_id
    }


async def create_portal_session(
    user_id: uuid.UUID,
    db: AsyncSession
) -> dict:
    """Create a customer portal session"""
    logger.info("creating_portal_for_user", user_id=str(user_id))
    
    # Get customer - must exist
    result = await db.execute(
        select(Customer).where(Customer.user_id == user_id)
    )
    customer = result.scalar_one_or_none()
    
    if not customer:
        logger.error("customer_not_found", user_id=str(user_id))
        raise ValueError("Customer not found")
    
    # Create portal session
    session = await stripe_service.create_portal_session(
        customer_id=customer.stripe_customer_id
    )
    
    logger.info(
        "portal_session_created",
        user_id=str(user_id),
        session_id=session.id
    )
    
    return {"portal_url": session.url}


async def cancel_subscription_at_period_end(
    user_id: uuid.UUID,
    db: AsyncSession
) -> dict:
    """Cancel user's active subscription at period end"""
    logger.info("canceling_subscription_at_period_end", user_id=str(user_id))
    
    # Get active subscription
    subscription = await get_active_subscription(user_id, db)
    
    if not subscription:
        logger.warning("no_active_subscription", user_id=str(user_id))
        raise ValueError("No active subscription found")
    
    # Update Stripe
    stripe_sub = await stripe_service.cancel_subscription(
        subscription.stripe_subscription_id
    )
    
    # Update database
    subscription.cancel_at_period_end = True
    subscription.updated_at = utc_now()
    await db.commit()
    await db.refresh(subscription)
    
    logger.info(
        "subscription_canceled_at_period_end",
        user_id=str(user_id),
        subscription_id=subscription.stripe_subscription_id
    )
    
    return {
        "status": "canceled",
        "subscription_id": subscription.stripe_subscription_id,
        "cancel_at_period_end": subscription.cancel_at_period_end
    }


async def get_user_subscriptions(
    user_id: uuid.UUID,
    db: AsyncSession
) -> Optional[dict]:
    """Get user's subscription info (latest one)"""
    subscription = await get_latest_subscription(user_id, db)
    
    if not subscription:
        logger.info("no_subscription", user_id=str(user_id))
        return {
            "plan": "free",
            "status": "active",
            "current_period_end": None,
            "cancel_at_period_end": False
        }
    
    return {
        "id": str(subscription.id),
        "plan": subscription.plan.value,
        "status": subscription.status.value,
        "current_period_end": subscription.current_period_end,
        "cancel_at_period_end": subscription.cancel_at_period_end,
        "current_period_start": subscription.current_period_start,
        "created_at": subscription.created_at
    }


async def get_user_invoices(
    user_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 10,
    offset: int = 0
) -> dict:
    """Get user's invoices"""
    logger.info("fetching_invoices", user_id=str(user_id), limit=limit, offset=offset)
    
    # Get customer
    result = await db.execute(
        select(Customer).where(Customer.user_id == user_id)
    )
    customer = result.scalar_one_or_none()
    
    if not customer:
        logger.warning("customer_not_found", user_id=str(user_id))
        return {"invoices": [], "total": 0, "limit": limit, "offset": offset}
    
    # Fetch from Stripe
    invoices = await stripe_service.list_invoices(
        customer_id=customer.stripe_customer_id,
        limit=limit,
        offset=offset
    )
    
    # Transform response
    invoice_items = [
        {
            "id": inv.id,
            "number": inv.number,
            "amount_paid": inv.amount_paid,
            "currency": inv.currency,
            "status": inv.status,
            "created": inv.created,
            "pdf_url": inv.invoice_pdf or inv.hosted_invoice_url
        }
        for inv in invoices
    ]
    
    logger.info("invoices_fetched", user_id=str(user_id), count=len(invoice_items))
    
    return {
        "invoices": invoice_items,
        "total": len(invoice_items),
        "limit": limit,
        "offset": offset
    }
