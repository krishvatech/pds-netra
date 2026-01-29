"""
Schemas for after-hours presence events published by edge.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class PresenceEvidence(BaseModel):
    snapshot_url: Optional[str] = None
    local_path: Optional[str] = None
    frame_ts: Optional[str] = None


class PresencePayload(BaseModel):
    count: int
    vehicle_plate: Optional[str] = None
    bbox: Optional[List[List[int]]] = None
    confidence: Optional[float] = None
    is_after_hours: Optional[bool] = None
    evidence: Optional[PresenceEvidence] = None


class PresenceEvent(BaseModel):
    schema_version: str = Field("1.0")
    event_id: str
    occurred_at: str
    timezone: str = Field("Asia/Kolkata")
    godown_id: str
    camera_id: str
    event_type: str
    payload: PresencePayload
    correlation_id: Optional[str] = None
