"""
ORM model for camera zones.
"""

from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, String, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Zone(Base):
    """
    Represents a polygonal zone defined for a camera.

    Zone coordinates are stored as a normalized polygon (0.0-1.0 for relative coords,
    or pixel values if > 1). The edge service scales them to actual frame resolution.
    """
    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    godown_id: Mapped[str] = mapped_column(String(64), index=True)  # Link to facility
    camera_id: Mapped[str] = mapped_column(String(64), index=True)  # Link to camera
    name: Mapped[str] = mapped_column(String(255))  # e.g., "Warehouse Floor"

    # Polygon as list of [x, y] points
    # Example: [[0.1, 0.2], [0.9, 0.2], [0.9, 0.8], [0.1, 0.8]]
    polygon: Mapped[list] = mapped_column(JSON)  # List[List[float]]

    # Calibration data (distance per pixel in this zone)
    pixels_per_meter: Mapped[float] = mapped_column(default=120.0)

    # Metadata
    enabled: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
