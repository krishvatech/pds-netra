"""
Alert reports for HQ digests.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class AlertReport(Base):
    __tablename__ = "alert_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scope: Mapped[str] = mapped_column(String(16), default="HQ")
    godown_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    email_html: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

