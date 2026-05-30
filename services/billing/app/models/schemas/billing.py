"""Request/response schemas for billing endpoints"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CheckoutRequest(BaseModel):
    """Request body for POST /billing/checkout"""
    plan: str = Field(..., pattern="^(pro|business)$", description="Subscription plan")


class CheckoutResponse(BaseModel):
    """Response for POST /billing/checkout"""
    checkout_url: str = Field(..., description="URL to Stripe checkout page")
    session_id: str = Field(..., description="Stripe checkout session ID")


class PortalResponse(BaseModel):
    """Response for POST /billing/portal"""
    portal_url: str = Field(..., description="URL to Stripe customer portal")


class CancelResponse(BaseModel):
    """Response for POST /billing/cancel"""
    status: str = Field(..., description="Cancellation status")
    subscription_id: str = Field(..., description="Stripe subscription ID")
    cancel_at_period_end: bool = Field(..., description="Whether cancellation is at period end")


class SubscriptionResponse(BaseModel):
    """Response for GET /billing/subscriptions/me"""
    id: Optional[str] = Field(None, description="Subscription ID")
    plan: str = Field(..., description="Plan name (pro, business, or free)")
    status: str = Field(..., description="Subscription status")
    current_period_end: Optional[datetime] = Field(None, description="End of current billing period")
    cancel_at_period_end: bool = Field(..., description="Whether cancellation is scheduled")


class InvoiceItemResponse(BaseModel):
    """Invoice item in list response"""
    id: str = Field(..., description="Stripe invoice ID")
    number: Optional[str] = Field(None, description="Invoice number")
    amount_paid: int = Field(..., description="Amount paid in cents")
    currency: str = Field(..., description="Currency code")
    status: str = Field(..., description="Invoice status")
    created: int = Field(..., description="Creation timestamp")
    pdf_url: Optional[str] = Field(None, description="PDF URL if available")


class InvoicesResponse(BaseModel):
    """Response for GET /billing/invoices"""
    invoices: List[InvoiceItemResponse] = Field(..., description="List of invoices")
    total: int = Field(..., description="Total number of invoices")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Pagination offset")


class ErrorResponse(BaseModel):
    """Standard error response"""
    detail: str = Field(..., description="Error message")
    code: Optional[str] = Field(None, description="Error code")
