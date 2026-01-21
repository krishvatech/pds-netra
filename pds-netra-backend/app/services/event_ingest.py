"""
Event ingestion service for PDS Netra backend.

This service exposes a function to handle incoming events from edge nodes.
It validates the event payload, upserts references such as godown and
camera if necessary, stores the raw event, and invokes the central rule
engine to create or update alerts.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models.godown import Godown, Camera
from ..models.event import Event
from ..schemas.event import EventIn
from .rule_engine import apply_rules


def handle_incoming_event(event_in: EventIn, db: Session) -> Event:
    """
    Handle an incoming event from an edge node.

    Parameters
    ----------
    event_in: EventIn
        The incoming event data parsed from JSON via Pydantic.
    db: Session
        SQLAlchemy session used for database operations.

    Returns
    -------
    Event
        The persisted ORM Event instance.
    """
    # Ensure godown exists
    godown = db.get(Godown, event_in.godown_id)
    if godown is None:
        godown = Godown(id=event_in.godown_id)
        db.add(godown)
        db.commit()
        db.refresh(godown)
    # Ensure camera exists
    camera = db.get(Camera, event_in.camera_id)
    if camera is None:
        camera = Camera(id=event_in.camera_id, godown_id=event_in.godown_id)
        db.add(camera)
        db.commit()
        db.refresh(camera)
    # Create Event instance
    event = Event(
        godown_id=event_in.godown_id,
        camera_id=event_in.camera_id,
        event_id_edge=event_in.event_id,
        event_type=event_in.event_type,
        severity_raw=event_in.severity,
        timestamp_utc=event_in.timestamp_utc,
        bbox=str(event_in.bbox) if event_in.bbox else None,
        track_id=event_in.track_id,
        image_url=event_in.image_url,
        clip_url=event_in.clip_url,
        meta=event_in.meta.model_dump(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    # Invoke rule engine
    apply_rules(db, event)
    return event
