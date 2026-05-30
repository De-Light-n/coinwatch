import uuid
from sqlalchemy import Column, String, DateTime, Integer, Enum, Uuid
from .base import Base, utc_now
import enum

class InvoiceStatus(str, enum.Enum):
    paid = "paid"
    open = "open"
    failed = "failed"
    void = "void"

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), nullable=False)
    stripe_invoice_id = Column(String, unique=True, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String, default="usd", nullable=False)
    status = Column(Enum(InvoiceStatus), nullable=False)
    pdf_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
