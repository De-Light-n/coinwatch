import uuid
from sqlalchemy import Column, String, DateTime, JSON, Uuid
from .base import Base, utc_now

class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stripe_event_id = Column(String, unique=True, index=True, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    processed_at = Column(DateTime, default=utc_now, nullable=False)
