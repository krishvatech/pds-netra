"""
API endpoints for accessing raw events and alerts.

Provides list endpoints with pagination and filters, and alert detail
responses used by the dashboard.
"""

from __future__ import annotations

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from ...core.db import get_db
from ...models.event import Event, Alert, AlertEventLink
from ...models.godown import Godown


router = APIRouter(prefix="/api/v1", tags=["events", "alerts"])


def _parse_bbox(bbox_raw: str | None) -> Optional[list[int]]:
    if not bbox_raw:
        return None
    try:
        # Stored as string representation of list
        if bbox_raw.startswith("[") and bbox_raw.endswith("]"):
            parts = bbox_raw.strip("[]").split(",")
            return [int(float(p.strip())) for p in parts if p.strip()]
    except Exception:
        return None
    return None


def _event_to_item(event: Event) -> dict:
    return {
        "id": event.id,
        "event_id": event.event_id_edge,
        "godown_id": event.godown_id,
        "camera_id": event.camera_id,
        "event_type": event.event_type,
        "severity": event.severity_raw,
        "timestamp_utc": event.timestamp_utc,
        "bbox": _parse_bbox(event.bbox),
        "track_id": event.track_id,
        "image_url": event.image_url,
        "clip_url": event.clip_url,
        "meta": event.meta or {},
    }


@router.get("/events")
def list_events(
    godown_id: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    plate_text: Optional[str] = Query(None),
    person_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    """List raw events with optional filters."""
    query = db.query(Event)
    if godown_id:
        query = query.filter(Event.godown_id == godown_id)
    if camera_id:
        query = query.filter(Event.camera_id == camera_id)
    if event_type:
        query = query.filter(Event.event_type == event_type)
    if severity:
        query = query.filter(Event.severity_raw == severity)
    # Support both date_from/date_to and start_time/end_time
    if date_from or start_time:
        query = query.filter(Event.timestamp_utc >= (date_from or start_time))
    if date_to or end_time:
        query = query.filter(Event.timestamp_utc <= (date_to or end_time))
    if plate_text:
        query = query.filter(Event.meta["plate_text"].astext == plate_text)
    if person_id:
        query = query.filter(Event.meta["person_id"].astext == person_id)
    total = query.count()
    events = (
        query.order_by(Event.timestamp_utc.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_event_to_item(e) for e in events],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/alerts")
def list_alerts(
    godown_id: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    """List alerts with optional filters."""
    query = db.query(Alert, Godown.district, Godown.name).join(
        Godown, Godown.id == Alert.godown_id, isouter=True
    )
    if godown_id:
        query = query.filter(Alert.godown_id == godown_id)
    if district:
        query = query.filter(Godown.district == district)
    if alert_type:
        query = query.filter(Alert.alert_type == alert_type)
    if severity:
        query = query.filter(Alert.severity_final == severity)
    if status:
        query = query.filter(Alert.status == status)
    if date_from:
        query = query.filter(Alert.start_time >= date_from)
    if date_to:
        query = query.filter(Alert.start_time <= date_to)
    total = query.count()
    rows = (
        query.order_by(Alert.start_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items: List[dict] = []
    for alert, godown_district, godown_name in rows:
        linked_ids = [link.event_id for link in alert.events]
        key_meta = {}
        if alert.events:
            try:
                key_meta = {
                    "zone_id": alert.events[0].event.meta.get("zone_id"),
                    "plate_text": alert.events[0].event.meta.get("plate_text"),
                }
            except Exception:
                key_meta = {}
        items.append(
            {
                "id": alert.id,
                "godown_id": alert.godown_id,
                "district": godown_district,
                "godown_name": godown_name,
                "camera_id": alert.camera_id,
                "alert_type": alert.alert_type,
                "severity_final": alert.severity_final,
                "start_time": alert.start_time,
                "end_time": alert.end_time,
                "status": alert.status,
                "summary": alert.summary,
                "count_events": len(linked_ids),
                "key_meta": key_meta or None,
            }
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/alerts/{alert_id}")
def get_alert(alert_id: int, db: Session = Depends(get_db)) -> dict:
    """Retrieve a single alert with its linked events."""
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    godown = db.get(Godown, alert.godown_id)
    linked_ids = [link.event_id for link in alert.events]
    events = [link.event for link in alert.events]
    key_meta = {}
    if events:
        key_meta = {
            "zone_id": events[0].meta.get("zone_id"),
            "plate_text": events[0].meta.get("plate_text"),
        }
    return {
        "id": alert.id,
        "godown_id": alert.godown_id,
        "district": godown.district if godown else None,
        "godown_name": godown.name if godown else None,
        "camera_id": alert.camera_id,
        "alert_type": alert.alert_type,
        "severity_final": alert.severity_final,
        "start_time": alert.start_time,
        "end_time": alert.end_time,
        "status": alert.status,
        "summary": alert.summary,
        "count_events": len(linked_ids),
        "linked_event_ids": linked_ids,
        "key_meta": key_meta or None,
        "events": [_event_to_item(e) for e in events],
    }
