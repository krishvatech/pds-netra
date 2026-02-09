"""
Event ingestion service for PDS Netra backend.

This service exposes a function to handle incoming events from edge nodes.
It validates the event payload, upserts references such as godown and
camera if necessary, stores the raw event, and invokes the central rule
engine to create or update alerts.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import List, Tuple

from sqlalchemy.orm import Session

from ..models.anpr_event import AnprEvent
from ..models.godown import Godown, Camera
from ..models.event import Event
from ..schemas.event import EventIn
from .rule_engine import apply_rules
from .vehicle_gate import handle_anpr_hit_event


logger = logging.getLogger("event_ingest")


def _point_in_polygon(x: float, y: float, polygon: List[Tuple[float, float]]) -> bool:
    num = len(polygon)
    j = num - 1
    inside = False
    for i in range(num):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi)
        if intersects:
            inside = not inside
        j = i
    return inside


def _bbox_in_zone(bbox: List[int], polygon: List[Tuple[float, float]]) -> bool:
    if len(bbox) != 4:
        return False
    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    if _point_in_polygon(cx, cy, polygon):
        return True
    corners = [(x1, y1), (x1, y2), (x2, y1), (x2, y2)]
    if any(_point_in_polygon(x, y, polygon) for x, y in corners):
        return True
    xs = [pt[0] for pt in polygon]
    ys = [pt[1] for pt in polygon]
    if not xs or not ys:
        return False
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return not (x2 < min_x or x1 > max_x or y2 < min_y or y1 > max_y)


def _infer_zone_id(bbox: List[int], zones_json: str | None) -> str | None:
    if not zones_json:
        return None
    try:
        zones = json.loads(zones_json)
    except Exception:
        return None
    if not isinstance(zones, list):
        return None
    for zone in zones:
        zone_id = zone.get("id") if isinstance(zone, dict) else None
        polygon = zone.get("polygon") if isinstance(zone, dict) else None
        if not zone_id or not isinstance(polygon, list):
            continue
        try:
            poly_pts = [tuple(map(float, pt)) for pt in polygon if isinstance(pt, list) and len(pt) == 2]
        except Exception:
            continue
        if not poly_pts:
            continue
        if _bbox_in_zone(bbox, poly_pts):
            return zone_id
    return None


ANPR_EDGE_EVENT_TYPES = {
    "ANPR_PLATE_VERIFIED",
    "ANPR_PLATE_ALERT",
    "ANPR_PLATE_DETECTED",
    "ANPR_TIME_VIOLATION",
    # Legacy/alternate payloads:
    "ANPR_HIT",
}


def _normalize_plate(text: str | None) -> str | None:
    if not text:
        return None
    out = "".join(ch for ch in str(text).upper() if ch.isalnum())
    return out or None


def _parse_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _maybe_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except Exception:
        return None


def _upsert_anpr_event(db: Session, *, event_in: EventIn, meta: dict) -> None:
    event_uuid = _maybe_uuid(event_in.event_id)
    if event_uuid:
        existing = db.query(AnprEvent).filter(AnprEvent.event_id == event_uuid).first()
        if existing:
            return

    plate_raw = (meta.get("plate_text") or meta.get("plate_raw") or "").strip() or None
    plate_norm = (meta.get("plate_norm") or _normalize_plate(plate_raw)) if plate_raw else None

    extra = meta.get("extra") if isinstance(meta.get("extra"), dict) else {}
    det_conf = _parse_float(extra.get("det_conf"))
    ocr_conf = _parse_float(extra.get("ocr_conf"))
    combined_conf = _parse_float(meta.get("confidence"))

    anpr = AnprEvent(
        event_id=event_uuid,
        godown_id=event_in.godown_id,
        camera_id=event_in.camera_id,
        zone_id=meta.get("zone_id"),
        timestamp_utc=event_in.timestamp_utc,
        plate_raw=plate_raw,
        plate_norm=plate_norm,
        match_status=(meta.get("match_status") or "UNKNOWN"),
        event_type=event_in.event_type,
        det_conf=det_conf,
        ocr_conf=ocr_conf,
        combined_conf=combined_conf,
        bbox=event_in.bbox,
        snapshot_url=event_in.image_url,
        meta=meta,
    )
    db.add(anpr)


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
    camera = (
        db.query(Camera)
        .filter(Camera.id == event_in.camera_id, Camera.godown_id == event_in.godown_id)
        .first()
    )
    if camera is None:
        camera = Camera(id=event_in.camera_id, godown_id=event_in.godown_id)
        db.add(camera)
        db.commit()
        db.refresh(camera)
    meta = event_in.meta.model_dump()
    if not meta.get("zone_id") and event_in.bbox:
        inferred_zone = _infer_zone_id(event_in.bbox, camera.zones_json)
        if inferred_zone:
            meta["zone_id"] = inferred_zone
    if event_in.event_type in {"ANPR_HIT", "FIRE_DETECTED"}:
        existing = (
            db.query(Event)
            .filter(
                Event.event_id_edge == event_in.event_id,
                Event.event_type == event_in.event_type,
                Event.godown_id == event_in.godown_id,
            )
            .first()
        )
        if existing:
            return existing
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
        meta=meta,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    if event.event_type in ANPR_EDGE_EVENT_TYPES:
        try:
            _upsert_anpr_event(db, event_in=event_in, meta=meta)
            db.commit()
        except Exception as exc:
            logger.exception(
                "ANPR upsert failed event_id=%s godown=%s camera=%s err=%s",
                event_in.event_id,
                event_in.godown_id,
                event_in.camera_id,
                exc,
            )
            db.rollback()

    if event.event_type in ANPR_EDGE_EVENT_TYPES:
        role = (camera.role or "").strip().upper()
        allow_gate_session = role in {"", "GATE_ANPR"}
        if allow_gate_session:
            try:
                handle_anpr_hit_event(
                    db,
                    godown_id=event.godown_id,
                    camera_id=event.camera_id,
                    event_id=event.event_id_edge,
                    occurred_at=event.timestamp_utc,
                    meta=event.meta or {},
                    image_url=event.image_url,
                )
                db.commit()
            except Exception as exc:
                logger.exception(
                    "ANPR gate session failed event_id=%s godown=%s camera=%s err=%s",
                    event_in.event_id,
                    event_in.godown_id,
                    event_in.camera_id,
                    exc,
                )
                db.rollback()
        else:
            logging.getLogger("event_ingest").info(
                "Ignoring ANPR gate session for non-gate camera: camera=%s role=%s",
                event.camera_id,
                role or "UNKNOWN",
            )
    # Invoke rule engine
    apply_rules(db, event)
    return event
