"""
ORM model for dispatch issues in PDS Netra backend.

Represents an issued dispatch request that must start within 24 hours.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class DispatchIssue(Base):
    __tablename__ = "dispatch_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    godown_id: Mapped[str] = mapped_column(String(64), index=True)
    camera_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    zone_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    issue_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="OPEN")
    started_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    alerted_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    alert_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("alerts.id"), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
