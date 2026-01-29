"""
ORM model for authorized users in PDS Netra backend.

Authorized users are personnel who are allowed to access godown facilities.
This model stores metadata about authorized users, which can be synced with
the edge face recognition system.
"""

from __future__ import annotations

from datetime import datetime
from sqlalchemy import Column, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base


class AuthorizedUser(Base):
    __tablename__ = "authorized_users"

    person_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)  # e.g. staff, admin, security
    godown_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("godowns.id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)