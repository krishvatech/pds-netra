from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CameraCreate(BaseModel):
    camera_name: str = Field(min_length=1, max_length=128)
    role: str = Field(min_length=1, max_length=64)
    rtsp_url: str = Field(min_length=1, max_length=512)
    is_active: bool = True
    user_id: UUID | None = None


class CameraUpdate(BaseModel):
    camera_name: str | None = Field(default=None, min_length=1, max_length=128)
    role: str | None = Field(default=None, min_length=1, max_length=64)
    rtsp_url: str | None = Field(default=None, min_length=1, max_length=512)
    is_active: bool | None = None


class CameraApprove(BaseModel):
    edge_id: UUID


class CameraOut(BaseModel):
    id: UUID
    camera_name: str
    role: str
    rtsp_url: str
    is_active: bool
    approval_status: str
    user_id: UUID
    edge_id: UUID | None = None
    owner_first_name: str | None = None
    owner_last_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
