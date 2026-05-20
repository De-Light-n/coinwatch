import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel
from app.models.watch import ConditionType


class WatcherCreate(BaseModel):
    name: str
    asset: str
    condition_type: ConditionType
    threshold: Decimal


class WatchResponseSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    asset: str
    condition_type: ConditionType
    threshold: Decimal
    interval_seconds: int
    is_active: bool
    last_checked_at: datetime | None
    last_triggered_at: datetime | None
    cooldown_seconds: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}