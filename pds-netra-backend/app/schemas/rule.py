"""
Pydantic schemas for configurable rules.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class RuleBase(BaseModel):
    godown_id: str
    camera_id: str
    zone_id: str
    type: str
    enabled: bool = True

    start_time: Optional[str] = None
    end_time: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    threshold_seconds: Optional[int] = None
    start_local: Optional[str] = None
    end_local: Optional[str] = None
    cooldown_seconds: Optional[int] = None
    require_active_dispatch_plan: Optional[bool] = None
    allowed_overage_percent: Optional[float] = None
    threshold_distance: Optional[int] = None
    allowed_plates: Optional[List[str]] = None
    blocked_plates: Optional[List[str]] = None


class RuleCreate(RuleBase):
    pass


class RuleUpdate(BaseModel):
    godown_id: Optional[str] = None
    camera_id: Optional[str] = None
    zone_id: Optional[str] = None
    type: Optional[str] = None
    enabled: Optional[bool] = None

    start_time: Optional[str] = None
    end_time: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    threshold_seconds: Optional[int] = None
    start_local: Optional[str] = None
    end_local: Optional[str] = None
    cooldown_seconds: Optional[int] = None
    require_active_dispatch_plan: Optional[bool] = None
    allowed_overage_percent: Optional[float] = None
    threshold_distance: Optional[int] = None
    allowed_plates: Optional[List[str]] = None
    blocked_plates: Optional[List[str]] = None


class RuleOut(RuleBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
