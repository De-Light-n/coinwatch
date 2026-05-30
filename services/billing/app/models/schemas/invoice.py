import uuid
from datetime import datetime
from pydantic import BaseModel
from .base import SchemaBase
from enum import Enum

class InvoiceStatus(str, Enum):
    paid = "paid"
    open = "open"
    failed = "failed"
    void = "void"

class InvoiceBase(SchemaBase):
    stripe_invoice_id: str
    amount_cents: int
    currency: str = "usd"
    status: InvoiceStatus
    pdf_url: str | None = None

class InvoiceCreate(InvoiceBase):
    user_id: uuid.UUID

class InvoiceOut(InvoiceBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
