"""Stripe webhook handler - Production-grade webhook processing"""
import structlog
import stripe
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.config import settings
from app.db import async_session_factory
from app.models import WebhookEvent
from app.services import webhook_service

logger = structlog.get_logger()
router = APIRouter()

@router.post("/stripe")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Stripe webhook endpoint - Production-grade implementation.

    Process:
    1. Read raw body (required for signature verification)
    2. Verify Stripe signature (SecurityError if invalid)
    3. Check idempotency (event already processed?)
    4. Return 200 immediately (Stripe expects < 5 sec response)
    5. Process event in background

    Security:
    - Signature verification prevents forgery
    - No PII logged
    - Idempotency prevents duplicate processing
    """
    try:
        # 1. Read raw body - MUST be raw bytes, not JSON parsed
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        if not sig_header:
            logger.warning("webhook_missing_signature")
            raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

        # 2. Verify Stripe signature
        try:
            event = stripe.Webhook.construct_event(
                payload,
                sig_header,
                settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            logger.warning("webhook_invalid_payload", error=str(e))
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            logger.warning("webhook_invalid_signature", error=str(e))
            raise HTTPException(status_code=400, detail="Invalid signature")

        event_id = event.get("id")
        event_type = event.get("type")

        logger.info("webhook_received", event_id=event_id, event_type=event_type)

        # 3. Idempotency check
        async with async_session_factory() as db:
            result = await db.execute(
                select(WebhookEvent).where(WebhookEvent.stripe_event_id == event_id)
            )
            existing = result.scalar_one_or_none()

        if existing:
            logger.info("webhook_already_processed", event_id=event_id)
            # Return 200 even for duplicates (idempotency)
            return JSONResponse(content={"status": "received"}, status_code=200)

        # 4. Return 200 immediately to Stripe (critical - must be < 5 sec)
        # Stripe has ~5 second timeout, we want to respond much faster
        response = JSONResponse(content={"status": "received"}, status_code=200)

        # 5. Add background task to process event asynchronously
        # Event dict is safe to pass - contains all we need for processing
        background_tasks.add_task(webhook_service.process_webhook_event, event.to_dict())

        logger.info("webhook_queued_for_processing", event_id=event_id)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("webhook_endpoint_error", error=str(e))
        # Even on unexpected errors, return 200 to avoid Stripe retries
        return JSONResponse(content={"status": "received"}, status_code=200)
