"""
Pydantic schemas for zone CRUD operations.
"""

from __future__ import annotations

from typing import List
from pydantic import BaseModel, Field
from datetime import datetime


class ZoneCreate(BaseModel):
    """Schema for creating a new zone from UI."""

    godown_id: str = Field(..., description="Parent facility ID")
    camera_id: str = Field(..., description="Camera ID where zone is drawn")
    name: str = Field(..., min_length=1, max_length=255, description="Zone name (e.g., 'Floor Area')")
    polygon: List[List[float]] = Field(
        ...,
        description="Polygon as list of [x, y] coordinates. Can be normalized (0-1) or pixels (>1)"
    )
    pixels_per_meter: float = Field(default=120.0, gt=0, description="Calibration factor")
    enabled: bool = Field(default=True)


class ZoneUpdate(BaseModel):
    """Schema for updating an existing zone."""

    name: str | None = None
    polygon: List[List[float]] | None = None
    pixels_per_meter: float | None = None
    enabled: bool | None = None


class ZoneOut(BaseModel):
    """Schema for zone response."""

    id: str
    godown_id: str
    camera_id: str
    name: str
    polygon: List[List[float]]
    pixels_per_meter: float
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
