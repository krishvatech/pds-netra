"""
ORM model for per-godown daily ANPR arrival plans.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base


class AnprDailyPlan(Base):
    __tablename__ = "anpr_daily_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    godown_id: Mapped[str] = mapped_column(String(64), index=True)
    plan_date: Mapped[date] = mapped_column(Date, index=True)

    timezone_name: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    expected_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cutoff_time_local: Mapped[time] = mapped_column(Time, default=time(18, 0))

    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)

    items: Mapped[list["AnprDailyPlanItem"]] = relationship(
        "AnprDailyPlanItem",
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
