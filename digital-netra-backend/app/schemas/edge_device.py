from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EdgeDeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    api_key: str = Field(min_length=1, max_length=255)
    is_active: bool = True
    location: str = Field(min_length=1, max_length=255)
    ip: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=255)
    user_id: UUID


class EdgeDeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    api_key: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None
    location: str | None = Field(default=None, min_length=1, max_length=255)
    ip: str | None = Field(default=None, min_length=1, max_length=64)
    password: str | None = Field(default=None, min_length=1, max_length=255)
    user_id: UUID | None = None


class EdgeDeviceOut(BaseModel):
    id: UUID
    name: str
    api_key: str
    is_active: bool
    location: str
    ip: str
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
