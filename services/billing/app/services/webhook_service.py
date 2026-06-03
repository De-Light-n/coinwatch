"""Webhook event processing - Handles Stripe events safely and reliably"""
import structlog
from datetime import datetime, timezone
from typing import Dict, Any
from sqlalchemy import select

from app.db import async_session_factory
from app.messaging.publisher import get_publisher
from app.models import (
    WebhookEvent, Subscription, Invoice, Customer,
    PlanEnum, StatusEnum, InvoiceStatus
)
from app.config import settings
from app.models.base import utc_now
from app.services import stripe_service

logger = structlog.get_logger()


async def process_webhook_event(event: Dict[str, Any]) -> None:
    """
    Process a single webhook event from Stripe.

    This function handles:
    1. Event persistence to database (for audit trail)
    2. Idempotency protection (handles duplicate events)
    3. Event-specific processing
    4. RabbitMQ publishing for downstream services
    5. Error handling and logging (safe, no PII)

    Called from webhook router in background task, so it can take time.
    """
    event_id = event.get("id")
    event_type = event.get("type")

    # Log only safe fields (no payload which may contain PII)
    logger.info(
        "processing_webhook",
        event_id=event_id,
        event_type=event_type,
    )

    try:
        # 1. Record event and check idempotency in a single transaction
        async with async_session_factory() as session:
            result = await session.execute(
                select(WebhookEvent).where(WebhookEvent.stripe_event_id == event_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                logger.info(
                    "webhook_duplicate_detected",
                    event_id=event_id,
                    event_type=event_type,
                )
                return  # Already processed, skip

            # Record the event for audit trail
            webhook_record = WebhookEvent(
                stripe_event_id=event_id,
                event_type=event_type,
                payload=event,
                processed_at=utc_now(),
            )
            session.add(webhook_record)
            await session.commit()

        # 2. Process event (outside transaction to avoid holding locks)
        publisher = await get_publisher()
        try:
            if event_type == "checkout.session.completed":
                await _handle_checkout_completed(event, publisher)

            elif event_type == "customer.subscription.updated":
                await _handle_subscription_updated(event, publisher)

            elif event_type == "customer.subscription.deleted":
                await _handle_subscription_deleted(event, publisher)

            elif event_type == "invoice.paid":
                await _handle_invoice_paid(event, publisher)

            elif event_type == "invoice.payment_failed":
                await _handle_payment_failed(event, publisher)

            else:
                # Log unhandled events but still succeed
                logger.info(
                    "webhook_unhandled_type",
                    event_id=event_id,
                    event_type=event_type,
                )

            logger.info(
                "webhook_processed",
                event_id=event_id,
                event_type=event_type,
            )

        finally:
            await publisher.close()

    except Exception as e:
        # Log error but don't re-raise (webhook has already returned 200)
        logger.error(
            "webhook_processing_failed",
            event_id=event_id,
            event_type=event_type,
            error=str(e),
            exc_info=True,
        )


async def _handle_checkout_completed(event: Dict[str, Any], publisher) -> None:
    """Handle checkout.session.completed - User completed payment"""
    try:
        session_obj = event["data"]["object"]
        customer_id = session_obj.get("customer")
        subscription_id = session_obj.get("subscription")

        if not subscription_id:
            logger.warning(
                "checkout_no_subscription",
                customer_id=customer_id,
            )
            return

        # Get full subscription info from Stripe (async-safe)
        stripe_subscription = await stripe_service.get_subscription(subscription_id)

        # Determine plan from price_id
        plan = _get_plan_by_price_id(stripe_subscription)

        async with async_session_factory() as session:
            # Find customer in database
            result = await session.execute(
                select(Customer).where(
                    Customer.stripe_customer_id == customer_id
                )
            )
            customer = result.scalar_one_or_none()

            if not customer:
                logger.warning(
                    "checkout_customer_not_found",
                    stripe_customer_id=customer_id,
                )
                return

            # Create or update subscription record
            result = await session.execute(
                select(Subscription).where(
                    Subscription.stripe_subscription_id == subscription_id
                )
            )
            subscription = result.scalar_one_or_none()

            status_value = stripe_subscription.status
            # Map Stripe status to our enum
            try:
                status_enum = StatusEnum(status_value)
            except ValueError:
                status_enum = StatusEnum.incomplete

            if not subscription:
                subscription = Subscription(
                    user_id=customer.user_id,
                    stripe_subscription_id=subscription_id,
                    plan=plan,
                    status=status_enum,
                    current_period_start=datetime.fromtimestamp(
                        stripe_subscription.current_period_start,
                        tz=timezone.utc
                    ).replace(tzinfo=None),
                    current_period_end=datetime.fromtimestamp(
                        stripe_subscription.current_period_end,
                        tz=timezone.utc
                    ).replace(tzinfo=None),
                    cancel_at_period_end=stripe_subscription.cancel_at_period_end or False,
                )
                session.add(subscription)
            else:
                subscription.plan = plan
                subscription.status = status_enum
                subscription.current_period_start = datetime.fromtimestamp(
                    stripe_subscription.current_period_start,
                    tz=timezone.utc
                ).replace(tzinfo=None)
                subscription.current_period_end = datetime.fromtimestamp(
                    stripe_subscription.current_period_end,
                    tz=timezone.utc
                ).replace(tzinfo=None)
                subscription.cancel_at_period_end = stripe_subscription.cancel_at_period_end or False

            await session.commit()

            # Publish event for other services (notifications, etc.)
            await publisher.publish("subscription.changed", {
                "user_id": str(customer.user_id),
                "plan": plan.value,
                "status": status_enum.value,
                "stripe_subscription_id": subscription_id,
            })

            logger.info(
                "checkout_completed_processed",
                user_id=str(customer.user_id),
                plan=plan.value,
                subscription_id=subscription_id,
            )

    except Exception as e:
        logger.error(
            "checkout_completed_error",
            error=str(e),
            exc_info=True,
        )


async def _handle_subscription_updated(event: Dict[str, Any], publisher) -> None:
    """Handle customer.subscription.updated - Subscription changed"""
    try:
        stripe_subscription = event["data"]["object"]
        subscription_id = stripe_subscription.get("id")

        # Determine plan
        plan = _get_plan_by_price_id_from_dict(stripe_subscription)

        async with async_session_factory() as session:
            result = await session.execute(
                select(Subscription).where(
                    Subscription.stripe_subscription_id == subscription_id
                )
            )
            subscription = result.scalar_one_or_none()

            if not subscription:
                logger.warning(
                    "subscription_updated_not_found",
                    stripe_subscription_id=subscription_id,
                )
                return

            status_value = stripe_subscription.get("status")
            try:
                status_enum = StatusEnum(status_value)
            except (ValueError, TypeError):
                status_enum = StatusEnum.incomplete

            subscription.plan = plan
            subscription.status = status_enum
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_subscription.get("current_period_start", 0),
                tz=timezone.utc
            ).replace(tzinfo=None)
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_subscription.get("current_period_end", 0),
                tz=timezone.utc
            ).replace(tzinfo=None)
            subscription.cancel_at_period_end = stripe_subscription.get("cancel_at_period_end", False)

            await session.commit()

            # Publish event
            await publisher.publish("subscription.changed", {
                "user_id": str(subscription.user_id),
                "plan": plan.value,
                "status": status_enum.value,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "stripe_subscription_id": subscription_id,
            })

            logger.info(
                "subscription_updated_processed",
                user_id=str(subscription.user_id),
                subscription_id=subscription_id,
                plan=plan.value,
                status=status_enum.value,
            )

    except Exception as e:
        logger.error(
            "subscription_updated_error",
            error=str(e),
            exc_info=True,
        )


async def _handle_subscription_deleted(event: Dict[str, Any], publisher) -> None:
    """Handle customer.subscription.deleted - Subscription canceled"""
    try:
        stripe_subscription = event["data"]["object"]
        subscription_id = stripe_subscription.get("id")

        async with async_session_factory() as session:
            result = await session.execute(
                select(Subscription).where(
                    Subscription.stripe_subscription_id == subscription_id
                )
            )
            subscription = result.scalar_one_or_none()

            if not subscription:
                logger.warning(
                    "subscription_deleted_not_found",
                    stripe_subscription_id=subscription_id,
                )
                return

            subscription.status = StatusEnum.canceled
            subscription.plan = PlanEnum.free  # Treat canceled as free plan

            await session.commit()

            # Publish event
            await publisher.publish("subscription.changed", {
                "user_id": str(subscription.user_id),
                "plan": "free",
                "status": "canceled",
                "stripe_subscription_id": subscription_id,
            })

            logger.info(
                "subscription_deleted_processed",
                user_id=str(subscription.user_id),
                subscription_id=subscription_id,
            )

    except Exception as e:
        logger.error(
            "subscription_deleted_error",
            error=str(e),
            exc_info=True,
        )


async def _handle_invoice_paid(event: Dict[str, Any], publisher) -> None:
    """Handle invoice.paid - Payment received"""
    try:
        invoice_data = event["data"]["object"]
        invoice_id = invoice_data.get("id")
        customer_id = invoice_data.get("customer")

        async with async_session_factory() as session:
            # Find customer
            result = await session.execute(
                select(Customer).where(
                    Customer.stripe_customer_id == customer_id
                )
            )
            customer = result.scalar_one_or_none()

            if not customer:
                logger.warning(
                    "invoice_paid_customer_not_found",
                    stripe_customer_id=customer_id,
                )
                return

            # Check if invoice already exists (idempotency)
            result = await session.execute(
                select(Invoice).where(
                    Invoice.stripe_invoice_id == invoice_id
                )
            )
            if result.scalar_one_or_none():
                logger.info(
                    "invoice_paid_already_recorded",
                    stripe_invoice_id=invoice_id,
                )
                return

            # Create invoice record
            invoice = Invoice(
                user_id=customer.user_id,
                stripe_invoice_id=invoice_id,
                amount_cents=invoice_data.get("amount_paid", 0),
                currency=invoice_data.get("currency", "usd"),
                status=InvoiceStatus.paid,
                pdf_url=invoice_data.get("hosted_invoice_url"),
            )
            session.add(invoice)
            await session.commit()

            # Publish event for notifications service
            await publisher.publish("invoice.paid", {
                "user_id": str(customer.user_id),
                "invoice_id": invoice_id,
                "amount_paid": invoice_data.get("amount_paid", 0),
                "currency": invoice_data.get("currency", "usd"),
            })

            logger.info(
                "invoice_paid_processed",
                user_id=str(customer.user_id),
                invoice_id=invoice_id,
                amount_cents=invoice_data.get("amount_paid", 0),
            )

    except Exception as e:
        logger.error(
            "invoice_paid_error",
            error=str(e),
            exc_info=True,
        )


async def _handle_payment_failed(event: Dict[str, Any], publisher) -> None:
    """Handle invoice.payment_failed - Payment failed"""
    try:
        invoice_data = event["data"]["object"]
        invoice_id = invoice_data.get("id")
        customer_id = invoice_data.get("customer")

        async with async_session_factory() as session:
            # Find customer
            result = await session.execute(
                select(Customer).where(
                    Customer.stripe_customer_id == customer_id
                )
            )
            customer = result.scalar_one_or_none()

            if not customer:
                logger.warning(
                    "payment_failed_customer_not_found",
                    stripe_customer_id=customer_id,
                )
                return

            # Publish event for notifications service
            await publisher.publish("payment.failed", {
                "user_id": str(customer.user_id),
                "invoice_id": invoice_id,
                "amount_due": invoice_data.get("amount_due", 0),
                "currency": invoice_data.get("currency", "usd"),
            })

            logger.info(
                "payment_failed_published",
                user_id=str(customer.user_id),
                invoice_id=invoice_id,
                amount_due=invoice_data.get("amount_due", 0),
            )

    except Exception as e:
        logger.error(
            "payment_failed_error",
            error=str(e),
            exc_info=True,
        )


def _get_plan_by_price_id(stripe_subscription) -> PlanEnum:
    """Get plan enum from Stripe subscription object"""
    try:
        if stripe_subscription.items.data:
            price_id = stripe_subscription.items.data[0].price.id
            if price_id == settings.STRIPE_PRO_PRICE_ID:
                return PlanEnum.pro
            elif price_id == settings.STRIPE_BUSINESS_PRICE_ID:
                return PlanEnum.business
    except (AttributeError, IndexError):
        pass
    return PlanEnum.free


def _get_plan_by_price_id_from_dict(subscription_dict: Dict) -> PlanEnum:
    """Get plan enum from Stripe subscription dict (from webhook payload)"""
    try:
        items = subscription_dict.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id")
            if price_id == settings.STRIPE_PRO_PRICE_ID:
                return PlanEnum.pro
            elif price_id == settings.STRIPE_BUSINESS_PRICE_ID:
                return PlanEnum.business
    except (TypeError, IndexError, KeyError):
        pass
    return PlanEnum.free
