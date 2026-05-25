import uuid
from datetime import datetime
from sqlalchemy import Numeric, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from app.models.base import Base


from decimal import Decimal

class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    watch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("watches.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    condition_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_alerts_watch_id", "watch_id"),
    )