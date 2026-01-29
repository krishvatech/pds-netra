"""
Pydantic schemas for after-hours policy administration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class AfterHoursPolicyUpdate(BaseModel):
    day_start: Optional[str] = None
    day_end: Optional[str] = None
    presence_allowed: Optional[bool] = None
    cooldown_seconds: Optional[int] = None
    enabled: Optional[bool] = None
    timezone: Optional[str] = None


class AfterHoursPolicyOut(BaseModel):
    id: Optional[str] = None
    godown_id: str
    timezone: str = Field("Asia/Kolkata")
    day_start: str
    day_end: str
    presence_allowed: bool
    cooldown_seconds: int
    enabled: bool
    source: str = "override"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AfterHoursPolicyAuditOut(BaseModel):
    id: str
    godown_id: str
    actor: Optional[str] = None
    source: str
    changes: dict
    before: Optional[dict] = None
    after: Optional[dict] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
