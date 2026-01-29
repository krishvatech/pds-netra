"""
Notification outbox for reliable delivery and audit.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Text, Index, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kind: Mapped[str] = mapped_column(String(16), default="ALERT")  # ALERT | REPORT
    # References alerts.public_id for stable external IDs
    alert_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("alerts.public_id", ondelete="CASCADE"), index=True, nullable=True)
    # References alert_reports.id for HQ digest sends
    report_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("alert_reports.id", ondelete="CASCADE"), index=True, nullable=True)
    channel: Mapped[str] = mapped_column(String(16))  # WHATSAPP | EMAIL
    target: Mapped[str] = mapped_column(String(256))
    subject: Mapped[str | None] = mapped_column(String(256), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    media_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")  # PENDING | SENT | FAILED | RETRYING
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("alert_id", "channel", "target", name="uq_notification_outbox_alert_channel_target"),
        UniqueConstraint("report_id", "channel", "target", name="uq_notification_outbox_report_channel_target"),
        Index("ix_notification_outbox_status_next_retry", "status", "next_retry_at"),
    )
