from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ZoneCreate(BaseModel):
    camera_id: UUID
    zone_name: str = Field(min_length=1, max_length=255)
    polygon: list[list[float]]
    is_active: bool = True


class ZoneUpdate(BaseModel):
    zone_name: str | None = Field(default=None, min_length=1, max_length=255)
    polygon: list[list[float]] | None = None
    is_active: bool | None = None


class ZoneOut(BaseModel):
    id: UUID
    camera_id: UUID
    zone_name: str
    polygon: list[list[float]]
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
