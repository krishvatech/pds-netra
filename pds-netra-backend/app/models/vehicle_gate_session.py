"""
ORM model for vehicle gate sessions tracked via ANPR hits.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class VehicleGateSession(Base):
    __tablename__ = "vehicle_gate_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    godown_id: Mapped[str] = mapped_column(String(64), index=True)
    anpr_camera_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    plate_raw: Mapped[str] = mapped_column(String(64), nullable=False)
    plate_norm: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    entry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), index=True, default="OPEN")
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exit_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reminders_sent: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_snapshot_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

