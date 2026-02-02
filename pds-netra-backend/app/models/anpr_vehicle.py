"""
ORM model for ANPR vehicle registry.

This table stores known vehicles per godown (plate + metadata) so the
dashboard can maintain a managed list rather than relying on rules JSON files.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class AnprVehicle(Base):
    __tablename__ = "anpr_vehicles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    godown_id: Mapped[str] = mapped_column(String(64), index=True)
    plate_raw: Mapped[str] = mapped_column(String(64), nullable=False)
    plate_norm: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    list_type: Mapped[str] = mapped_column(String(16), default="WHITELIST")
    transporter: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
