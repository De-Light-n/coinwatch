"""Billing router - handles subscription and payment endpoints"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, User, get_db
from app.models.schemas.billing import (
    CheckoutRequest, CheckoutResponse, PortalResponse,
    CancelResponse, SubscriptionResponse, InvoicesResponse,
    ErrorResponse
)
from app.services import subscription_service
from app.services import stripe_service

logger = structlog.get_logger()
router = APIRouter()


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid plan"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        502: {"model": ErrorResponse, "description": "Stripe error"},
    }
)
async def checkout(
    body: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Stripe Checkout Session for subscription upgrade.
    
    Requires JWT authentication. If user doesn't have a Stripe customer,
    one will be created automatically.
    
    Test cards:
    - Success: 4242 4242 4242 4242
    - Auth required: 4000 0027 6000 3184
    - Declined: 4000 0000 0000 0002
    """
    try:
        result = await subscription_service.create_checkout_session(
            user_id=user.id,
            email=user.email,
            plan=body.plan,
            db=db
        )
        
        logger.info(
            "checkout_endpoint_success",
            user_id=str(user.id),
            plan=body.plan,
            session_id=result["session_id"]
        )
        
        return CheckoutResponse(
            checkout_url=result["checkout_url"],
            session_id=result["session_id"]
        )
    
    except ValueError as e:
        logger.error("checkout_validation_error", error=str(e), user_id=str(user.id))
        raise HTTPException(status_code=400, detail=str(e))
    
    except stripe_service.CardError as e:
        logger.error("checkout_card_error", user_id=str(user.id), error=str(e))
        raise HTTPException(
            status_code=402,
            detail="Card declined. Please check your card details."
        )
    
    except stripe_service.RateLimitError as e:
        logger.error("checkout_rate_limit", user_id=str(user.id))
        raise HTTPException(status_code=429, detail="Too many requests")
    
    except stripe_service.StripeError as e:
        logger.error("checkout_stripe_error", user_id=str(user.id), error=str(e))
        raise HTTPException(
            status_code=502,
            detail=f"Payment processing error: {str(e)}"
        )
    
    except Exception as e:
        logger.exception("checkout_unexpected_error", user_id=str(user.id))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/portal",
    response_model=PortalResponse,
    responses={
        400: {"model": ErrorResponse, "description": "No customer found"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        502: {"model": ErrorResponse, "description": "Stripe error"},
    }
)
async def portal(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a link to the Stripe Customer Portal for subscription management.
    
    Users can:
    - Update payment method
    - View invoices
    - Cancel subscription
    - Change subscription plan
    """
    try:
        result = await subscription_service.create_portal_session(
            user_id=user.id,
            db=db
        )
        
        logger.info("portal_endpoint_success", user_id=str(user.id))
        
        return PortalResponse(portal_url=result["portal_url"])
    
    except ValueError as e:
        logger.error("portal_validation_error", user_id=str(user.id), error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    
    except stripe_service.StripeError as e:
        logger.error("portal_stripe_error", user_id=str(user.id), error=str(e))
        raise HTTPException(status_code=502, detail="Failed to create portal session")
    
    except Exception as e:
        logger.exception("portal_unexpected_error", user_id=str(user.id))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/subscriptions/me",
    response_model=SubscriptionResponse
)
async def get_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user's subscription status.
    
    Returns active subscription or 'free' plan if no subscription.
    """
    try:
        result = await subscription_service.get_user_subscriptions(
            user_id=user.id,
            db=db
        )
        
        logger.info("get_subscription_success", user_id=str(user.id), plan=result.get("plan"))
        
        return SubscriptionResponse(**result)
    
    except Exception as e:
        logger.exception("get_subscription_error", user_id=str(user.id))
        raise HTTPException(status_code=500, detail="Failed to fetch subscription")


@router.post(
    "/cancel",
    response_model=CancelResponse,
    responses={
        400: {"model": ErrorResponse, "description": "No active subscription"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        502: {"model": ErrorResponse, "description": "Stripe error"},
    }
)
async def cancel_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Cancel user's subscription at the end of the current billing period.
    
    The user will retain access until the current period ends.
    """
    try:
        result = await subscription_service.cancel_subscription_at_period_end(
            user_id=user.id,
            db=db
        )
        
        logger.info("cancel_subscription_success", user_id=str(user.id))
        
        return CancelResponse(**result)
    
    except ValueError as e:
        logger.error("cancel_validation_error", user_id=str(user.id), error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    
    except stripe_service.StripeError as e:
        logger.error("cancel_stripe_error", user_id=str(user.id), error=str(e))
        raise HTTPException(status_code=502, detail="Failed to cancel subscription")
    
    except Exception as e:
        logger.exception("cancel_unexpected_error", user_id=str(user.id))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/invoices",
    response_model=InvoicesResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        502: {"model": ErrorResponse, "description": "Stripe error"},
    }
)
async def get_invoices(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    Get user's invoice history with pagination.
    
    Returns list of invoices with amounts, dates, and PDF URLs.
    """
    try:
        result = await subscription_service.get_user_invoices(
            user_id=user.id,
            db=db,
            limit=limit,
            offset=offset
        )
        
        logger.info(
            "get_invoices_success",
            user_id=str(user.id),
            count=len(result["invoices"])
        )
        
        return InvoicesResponse(**result)
    
    except stripe_service.StripeError as e:
        logger.error("invoices_stripe_error", user_id=str(user.id), error=str(e))
        raise HTTPException(status_code=502, detail="Failed to fetch invoices")
    
    except Exception as e:
        logger.exception("invoices_unexpected_error", user_id=str(user.id))
        raise HTTPException(status_code=500, detail="Internal server error")