"""
ORM model for daily plan items (per-vehicle/per-plate rows).
"""

from __future__ import annotations

import uuid
from datetime import datetime, time

from sqlalchemy import DateTime, ForeignKey, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base


class AnprDailyPlanItem(Base):
    __tablename__ = "anpr_daily_plan_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("anpr_daily_plans.id"), index=True)

    vehicle_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("anpr_vehicles.id"), nullable=True)
    plate_raw: Mapped[str] = mapped_column(String(64), nullable=False)
    plate_norm: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    expected_by_local: Mapped[time | None] = mapped_column(Time, nullable=True)
    status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # manual override
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    plan: Mapped["AnprDailyPlan"] = relationship("AnprDailyPlan", back_populates="items")
