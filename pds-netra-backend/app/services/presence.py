"""
Presence event ingestion for after-hours detection.
"""

from __future__ import annotations

from typing import Tuple

from sqlalchemy.orm import Session

from ..models.event import Event
from ..schemas.presence import PresenceEventIn
from .after_hours import get_after_hours_policy, is_after_hours
from .rule_engine import apply_rules


def ingest_presence_event(db: Session, event_in: PresenceEventIn) -> Tuple[Event, bool]:
    if event_in.event_type not in {"PERSON_DETECTED", "VEHICLE_DETECTED", "ANPR_HIT"}:
        raise ValueError("Unsupported presence event type")
    existing = db.query(Event).filter(Event.event_id_edge == event_in.event_id).first()
    if existing:
        return existing, False
    policy = get_after_hours_policy(db, event_in.godown_id)
    after_hours = is_after_hours(event_in.occurred_at, policy)
    payload = event_in.payload
    evidence = payload.evidence
    meta = {
        "schema_version": event_in.schema_version,
        "timezone": event_in.timezone,
        "count": payload.count,
        "vehicle_plate": payload.vehicle_plate,
        "confidence": payload.confidence,
        "bbox": payload.bbox,
        "is_after_hours": after_hours,
        "correlation_id": event_in.correlation_id,
        "evidence": evidence.model_dump() if evidence else None,
    }
    if payload.vehicle_plate:
        meta["plate_text"] = payload.vehicle_plate
    severity = "critical" if after_hours else "info"
    event = Event(
        godown_id=event_in.godown_id,
        camera_id=event_in.camera_id,
        event_id_edge=event_in.event_id,
        event_type=event_in.event_type,
        severity_raw=severity,
        timestamp_utc=event_in.occurred_at,
        bbox=None,
        track_id=None,
        image_url=evidence.snapshot_url if evidence else None,
        clip_url=None,
        meta=meta,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    apply_rules(db, event)
    return event, True
