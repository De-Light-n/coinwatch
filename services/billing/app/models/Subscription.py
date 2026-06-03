import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean, Enum, ForeignKey, Uuid
from sqlalchemy.orm import relationship
from .base import Base, utc_now
import enum

class PlanEnum(str, enum.Enum):
    free = "free"
    pro = "pro"
    business = "business"

class StatusEnum(str, enum.Enum):
    active = "active"
    past_due = "past_due"
    canceled = "canceled"
    trialing = "trialing"
    incomplete = "incomplete"

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("customers.user_id"), index=True, nullable=False)
    stripe_subscription_id = Column(String, unique=True, index=True, nullable=False)
    plan = Column(Enum(PlanEnum), nullable=False)
    status = Column(Enum(StatusEnum), nullable=False)
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    customer = relationship("Customer", backref="subscriptions")
