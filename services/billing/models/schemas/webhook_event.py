import uuid
from datetime import datetime
from pydantic import BaseModel
from .base import SchemaBase

class WebhookEventBase(SchemaBase):
    stripe_event_id: str
    event_type: str
    payload: dict

class WebhookEventCreate(WebhookEventBase):
    pass

class WebhookEventOut(WebhookEventBase):
    id: uuid.UUID
    processed_at: datetime
