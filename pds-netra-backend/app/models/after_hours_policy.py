"""
ORM model for after-hours presence policies.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class AfterHoursPolicy(Base):
    __tablename__ = "after_hours_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    godown_id: Mapped[str] = mapped_column(String(64), index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    day_start: Mapped[str] = mapped_column(String(8), default="09:00")
    day_end: Mapped[str] = mapped_column(String(8), default="19:00")
    presence_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=120)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
