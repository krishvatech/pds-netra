"""
Pydantic models for events and health reports published by the edge node.

These models mirror the JSON contract specified for PDS Netra events and
health messages. Using Pydantic ensures that data is validated and
serialized consistently to JSON when publishing messages via MQTT.
"""

from __future__ import annotations

from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class MetaModel(BaseModel):
    """Additional metadata associated with an event."""

    zone_id: Optional[str] = None
    rule_id: str
    confidence: float
    # Optional movement type for bag movement events (e.g. "AFTER_HOURS", "GENERIC").
    movement_type: Optional[str] = None
    # Optional number plate string for ANPR events.
    plate_text: Optional[str] = None
    # Optional match status for ANPR events (e.g. "WHITELIST", "BLACKLIST", "UNKNOWN").
    match_status: Optional[str] = None
    # Optional reason for tamper or health events (e.g. "BLACK_FRAME", "CAMERA_MOVED").
    reason: Optional[str] = None
    extra: Dict[str, str] = Field(default_factory=dict)


class EventModel(BaseModel):
    """Representation of a structured event emitted by the edge node."""

    godown_id: str
    camera_id: str
    event_id: str
    event_type: str
    severity: str
    timestamp_utc: str
    bbox: Optional[List[int]] = None
    track_id: Optional[int] = None
    image_url: Optional[str] = None
    clip_url: Optional[str] = None
    meta: MetaModel


class CameraStatusModel(BaseModel):
    """Per-camera status entry for health heartbeats."""

    camera_id: str
    online: Optional[bool] = None
    last_frame_utc: Optional[str] = None
    last_tamper_reason: Optional[str] = None
    fps_estimate: Optional[float] = None


class HealthModel(BaseModel):
    """Health heartbeat message describing the state of the edge node."""

    godown_id: str
    device_id: str
    status: str
    online_cameras: int
    total_cameras: int
    timestamp_utc: str
    # Detailed camera status list. Each entry describes one camera's health.
    camera_status: Optional[List[CameraStatusModel]] = None


__all__ = [
    'MetaModel',
    'EventModel',
    'CameraStatusModel',
    'HealthModel',
]
