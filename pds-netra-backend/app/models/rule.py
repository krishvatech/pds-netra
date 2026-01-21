"""
Data models for central rule configuration (optional).

This module defines ORM models for storing rule definitions that can
modify the behaviour of the central rule engine. These rules can be
fetched at runtime and applied to events. The implementation here is
minimal; for a production system, rule conditions and actions would
likely be more complex.
"""

from __future__ import annotations

from sqlalchemy import Integer, String, Column, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class CentralRule(Base):
    __tablename__ = "central_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # JSON structure describing conditions and actions
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)
