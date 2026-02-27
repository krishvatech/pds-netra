"""
HTTP fallback for edge events.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...schemas.watchlist import FaceMatchEventIn
from ...schemas.event import EventIn
from ...schemas.presence import PresenceEventIn
from ...services.watchlist import ingest_face_match_event
from ...services.presence import ingest_presence_event
from ...services.event_ingest import handle_incoming_event
from ...core.request_limits import enforce_json_body_limit


router = APIRouter(prefix="/api/v1/edge", tags=["edge"])

ANPR_EVENT_TYPES = {
    "ANPR_PLATE_VERIFIED",
    "ANPR_PLATE_ALERT",
    "ANPR_PLATE_DETECTED",
    "ANPR_TIME_VIOLATION",
    "ANPR_HIT",
}


@router.post("/events")
def ingest_edge_event(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    request=Depends(enforce_json_body_limit),
) -> dict:
    event_type = payload.get("event_type") if isinstance(payload, dict) else None
    if event_type == "FACE_MATCH":
        face_event = FaceMatchEventIn.model_validate(payload)
        if face_event.schema_version != "1.0":
            raise HTTPException(status_code=400, detail="Unsupported event schema")
        event, created_alert = ingest_face_match_event(db, face_event)
        return {"status": "ok", "event_id": event.id, "alert_created": created_alert}
    if event_type in {"PERSON_DETECTED", "VEHICLE_DETECTED", "ANPR_HIT"}:
        presence_event = PresenceEventIn.model_validate(payload)
        if presence_event.schema_version != "1.0":
            raise HTTPException(status_code=400, detail="Unsupported event schema")
        try:
            event, created = ingest_presence_event(db, presence_event)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "event_id": event.id, "created": created}
    if event_type in {"ANIMAL_INTRUSION", "ANIMAL_DETECTED", "FIRE_DETECTED", "MOBILE_PHONE_USAGE"} | ANPR_EVENT_TYPES:
        event_in = EventIn.model_validate(payload)
        event = handle_incoming_event(event_in, db)
        return {"status": "ok", "event_id": event.id}
    raise HTTPException(status_code=400, detail="Unsupported event schema")
