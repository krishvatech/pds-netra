"""
Pydantic schemas for events in PDS Netra backend.

``EventIn`` describes the structure of raw events received from the edge
nodes via MQTT or HTTP. ``EventOut`` is used when returning events
via the REST API.
"""

from __future__ import annotations

from typing import List, Optional, Dict
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class MetaIn(BaseModel):
    zone_id: Optional[str]
    rule_id: Optional[str]
    confidence: Optional[float]
    movement_type: Optional[str] = None
    plate_text: Optional[str] = None
    plate_norm: Optional[str] = None
    direction: Optional[str] = None
    match_status: Optional[str] = None
    reason: Optional[str] = None
    person_id: Optional[str] = None
    person_name: Optional[str] = None
    person_role: Optional[str] = None
    animal_species: Optional[str] = None
    animal_count: Optional[int] = None
    animal_confidence: Optional[float] = None
    animal_is_night: Optional[bool] = None
    animal_bboxes: Optional[List[List[int]]] = None
    fire_classes: Optional[List[str]] = None
    fire_confidence: Optional[float] = None
    fire_bboxes: Optional[List[List[int]]] = None
    fire_model_name: Optional[str] = None
    fire_model_version: Optional[str] = None
    fire_weights_id: Optional[str] = None
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

    model_config = ConfigDict(from_attributes=True)
