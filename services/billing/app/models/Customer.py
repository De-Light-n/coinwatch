import uuid
from sqlalchemy import Column, String, DateTime, Uuid
from .base import Base, utc_now

class Customer(Base):
    __tablename__ = "customers"

    user_id = Column(Uuid(as_uuid=True), primary_key=True)
    stripe_customer_id = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
