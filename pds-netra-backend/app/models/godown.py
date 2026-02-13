"""
ORM models for godowns and cameras in PDS Netra backend.

Godown represents a storage facility. Camera represents a surveillance
camera associated with a godown. Each camera can cover multiple
zones defined at the edge. These models are referenced by events and
alerts.
"""

from __future__ import annotations

from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base


class Godown(Base):
    __tablename__ = "godowns"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    district: Mapped[str | None] = mapped_column(String(128), nullable=True)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("app_users.id"),
        nullable=True,
        index=True,
    )

    cameras: Mapped[list[Camera]] = relationship("Camera", back_populates="godown", cascade="all, delete-orphan")


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    godown_id: Mapped[str] = mapped_column(String(64), ForeignKey("godowns.id"), primary_key=True, index=True)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)  # e.g. GATE, AISLE, PERIMETER
    rtsp_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    zones_json: Mapped[str | None] = mapped_column(String, nullable=True)
    modules_json: Mapped[str | None] = mapped_column(String, nullable=True)

    godown: Mapped[Godown] = relationship("Godown", back_populates="cameras")
