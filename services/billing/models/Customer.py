import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from .base import Base

class Customer(Base):
    __tablename__ = "customers"

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    stripe_customer_id = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
