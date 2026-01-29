"""
Recipients for alert notifications.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class NotificationRecipient(Base):
    __tablename__ = "notification_recipients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    role: Mapped[str] = mapped_column(String(32))  # HQ, GODOWN_MANAGER
    channel: Mapped[str] = mapped_column(String(32))  # EMAIL, WHATSAPP
    destination: Mapped[str] = mapped_column(String(256))
    godown_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
