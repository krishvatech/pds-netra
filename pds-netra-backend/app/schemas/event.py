"""
Pydantic schemas for events in PDS Netra backend.

``EventIn`` describes the structure of raw events received from the edge
nodes via MQTT or HTTP. ``EventOut`` is used when returning events
via the REST API.
"""

from __future__ import annotations

from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime


class MetaIn(BaseModel):
    zone_id: Optional[str]
    rule_id: Optional[str]
    confidence: Optional[float]
    movement_type: Optional[str] = None
    plate_text: Optional[str] = None
    match_status: Optional[str] = None
    reason: Optional[str] = None
    extra: Dict[str, str] = Field(default_factory=dict)


class EventIn(BaseModel):
    godown_id: str
    camera_id: str
    event_id: str
    event_type: str
    severity: str
    timestamp_utc: datetime
    bbox: Optional[List[int]] = None
    track_id: Optional[int] = None
    image_url: Optional[str] = None
    clip_url: Optional[str] = None
    meta: MetaIn


class EventOut(BaseModel):
    id: int
    godown_id: str
    camera_id: str
    event_id_edge: str
    event_type: str
    severity_raw: str
    timestamp_utc: datetime
    bbox: Optional[str]
    track_id: Optional[int]
    image_url: Optional[str]
    clip_url: Optional[str]
    meta: Dict

    class Config:
        orm_mode = True
