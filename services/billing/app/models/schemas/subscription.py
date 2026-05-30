import uuid
from datetime import datetime
from pydantic import BaseModel
from .base import SchemaBase
from enum import Enum

class PlanEnum(str, Enum):
    pro = "pro"
    business = "business"

class StatusEnum(str, Enum):
    active = "active"
    past_due = "past_due"
    canceled = "canceled"
    trialing = "trialing"
    incomplete = "incomplete"

class SubscriptionBase(SchemaBase):
    stripe_subscription_id: str
    plan: PlanEnum
    status: StatusEnum
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False

class SubscriptionCreate(SubscriptionBase):
    user_id: uuid.UUID

class SubscriptionOut(SubscriptionBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
