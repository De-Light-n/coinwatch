import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, Numeric, DateTime, Enum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import  Mapped, mapped_column
import enum
from decimal import Decimal

from app.models.base import Base



class ConditionType(str, enum.Enum):
    price_above = "price_above"
    price_below = "price_below"
    percent_change = "percent_change"
    market_cap_rank = "market_cap_rank"

class Watch(Base):
    __tablename__ = "watches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),nullable=False)
    name: Mapped[str] = mapped_column(String,nullable=False)
    asset: Mapped[str] = mapped_column(String,nullable=False)
    condition_type: Mapped[ConditionType] = mapped_column(Enum(ConditionType),nullable=False) 
    threshold: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)  
    interval_seconds: Mapped[int] = mapped_column(Integer,nullable=False)
    is_active:Mapped[bool] = mapped_column(Boolean,default=True)
    last_checked_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True),nullable=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=1800, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_watches_user_id_is_active", "user_id", "is_active"),
        Index("ix_watches_asset_is_active", "asset", "is_active"),
    )
