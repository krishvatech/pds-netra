# pds/backend/app/api/v1/events.py

"""
API endpoints for accessing raw events and alerts.

Provides list endpoints with pagination and filters, and alert detail
responses used by the dashboard.
"""

from __future__ import annotations

from typing import List, Optional
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.auth import get_optional_user
from ...models.event import Event, Alert, AlertEventLink
from ...models.godown import Godown, Camera
from ...models.alert_action import AlertAction
from ...models.notification_outbox import NotificationOutbox
from ...schemas.alert_action import AlertActionCreate, AlertActionOut
from ...schemas.notifications import NotificationDeliveryOut
from ...services.ack_tokens import verify_raw_token
from ...core.pagination import clamp_page_size, set_pagination_headers


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


def _point_in_polygon(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
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


def _bbox_in_zone(bbox: list[int], polygon: list[tuple[float, float]]) -> bool:
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


def _infer_zone_id(db: Session, event: Event) -> Optional[str]:
    bbox = _parse_bbox(event.bbox)
    if not bbox:
        return None
    camera = (
        db.query(Camera)
        .filter(Camera.id == event.camera_id, Camera.godown_id == event.godown_id)
        .first()
    )
    if not camera or not camera.zones_json:
        return None
    try:
        zones = json.loads(camera.zones_json)
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


def _event_to_item(event: Event) -> dict:
    image_url = event.image_url
    if image_url and "/media/snapshots/" in image_url:
        try:
            parsed = urlparse(image_url)
            path = parsed.path
            if path.startswith("/media/snapshots/"):
                rel = path.replace("/media/snapshots/", "")
                snapshots_root = Path(__file__).resolve().parents[3] / "data" / "snapshots"
                file_path = snapshots_root / rel
                if not file_path.exists():
                    image_url = None
        except Exception:
            pass
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
        "image_url": image_url,
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
    page_size: int = Query(50, ge=1),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    """List raw events with optional filters."""
    page_size = clamp_page_size(page_size)
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
    updated = False
    for event in events:
        meta = event.meta or {}
        if not meta.get("zone_id") and event.bbox:
            inferred_zone = _infer_zone_id(db, event)
            if inferred_zone:
                meta = dict(meta)
                meta["zone_id"] = inferred_zone
                event.meta = meta
                updated = True
    if updated:
        db.commit()
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
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
) -> dict:
    """List alerts with optional filters."""
    page_size = clamp_page_size(page_size)
    query = db.query(Alert, Godown.district, Godown.name).join(
        Godown, Godown.id == Alert.godown_id, isouter=True
    )
    if user and user.role.upper() == "GODOWN_MANAGER" and user.godown_id:
        query = query.filter(Alert.godown_id == user.godown_id)
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
    sort_time = func.coalesce(Alert.end_time, Alert.start_time)
    rows = (
        query.order_by(sort_time.desc())
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
                meta = alert.events[0].event.meta or {}
                extra = meta.get("extra") or {}
                if not isinstance(extra, dict):
                    extra = {}
                key_meta = {
                    "zone_id": meta.get("zone_id"),
                    "plate_text": meta.get("plate_text"),
                    "movement_type": meta.get("movement_type"),
                    "reason": meta.get("reason"),
                    "run_id": extra.get("run_id"),
                }
            except Exception:
                key_meta = {}
        if alert.alert_type == "BLACKLIST_PERSON_MATCH":
            extra = alert.extra or {}
            key_meta.update(
                {
                    "person_id": extra.get("person_id"),
                    "person_name": extra.get("person_name"),
                    "match_score": extra.get("match_score"),
                    "snapshot_url": extra.get("snapshot_url"),
                }
            )
        if alert.alert_type in {"AFTER_HOURS_PERSON_PRESENCE", "AFTER_HOURS_VEHICLE_PRESENCE"}:
            extra = alert.extra or {}
            key_meta.update(
                {
                    "detected_count": extra.get("detected_count"),
                    "vehicle_plate": extra.get("vehicle_plate"),
                    "snapshot_url": extra.get("snapshot_url"),
                    "occurred_at": extra.get("occurred_at"),
                    "last_seen_at": extra.get("last_seen_at"),
                }
            )
        if alert.alert_type == "ANIMAL_INTRUSION":
            extra = alert.extra or {}
            key_meta.update(
                {
                    "animal_species": extra.get("animal_species"),
                    "animal_count": extra.get("animal_count"),
                    "animal_confidence": extra.get("animal_confidence"),
                    "animal_is_night": extra.get("animal_is_night"),
                    "snapshot_url": extra.get("snapshot_url"),
                    "occurred_at": extra.get("occurred_at"),
                    "last_seen_at": extra.get("last_seen_at"),
                }
            )
        if alert.alert_type == "FIRE_DETECTED":
            extra = alert.extra or {}
            key_meta.update(
                {
                    "fire_classes": extra.get("fire_classes"),
                    "fire_confidence": extra.get("fire_confidence"),
                    "fire_model_name": extra.get("fire_model_name"),
                    "fire_model_version": extra.get("fire_model_version"),
                    "fire_weights_id": extra.get("fire_weights_id"),
                    "snapshot_url": extra.get("snapshot_url"),
                    "occurred_at": extra.get("occurred_at"),
                    "last_seen_at": extra.get("last_seen_at"),
                }
            )
        if alert.alert_type == "DISPATCH_MOVEMENT_DELAY":
            extra = alert.extra or {}
            key_meta.update(
                {
                    "plate_norm": extra.get("plate_norm"),
                    "plate_raw": extra.get("plate_raw"),
                    "entry_at": extra.get("entry_at"),
                    "age_hours": extra.get("age_hours"),
                    "threshold_hours": extra.get("threshold_hours"),
                    "last_seen_at": extra.get("last_seen_at"),
                    "snapshot_url": extra.get("snapshot_url"),
                }
            )
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
def get_alert(alert_id: int, db: Session = Depends(get_db), user=Depends(get_optional_user)) -> dict:
    """Retrieve a single alert with its linked events."""
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if user and user.role.upper() == "GODOWN_MANAGER" and user.godown_id:
        if alert.godown_id != user.godown_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    godown = db.get(Godown, alert.godown_id)
    linked_ids = [link.event_id for link in alert.events]
    events = [link.event for link in alert.events]
    key_meta = {}
    if events:
        meta = events[0].meta or {}
        extra = meta.get("extra") or {}
        if not isinstance(extra, dict):
            extra = {}
        key_meta = {
            "zone_id": meta.get("zone_id"),
            "plate_text": meta.get("plate_text"),
            "movement_type": meta.get("movement_type"),
            "reason": meta.get("reason"),
            "run_id": extra.get("run_id"),
        }
    if alert.alert_type == "BLACKLIST_PERSON_MATCH":
        extra = alert.extra or {}
        key_meta.update(
            {
                "person_id": extra.get("person_id"),
                "person_name": extra.get("person_name"),
                "match_score": extra.get("match_score"),
                "snapshot_url": extra.get("snapshot_url"),
            }
        )
    if alert.alert_type in {"AFTER_HOURS_PERSON_PRESENCE", "AFTER_HOURS_VEHICLE_PRESENCE"}:
        extra = alert.extra or {}
        key_meta.update(
            {
                "detected_count": extra.get("detected_count"),
                "vehicle_plate": extra.get("vehicle_plate"),
                "snapshot_url": extra.get("snapshot_url"),
                "occurred_at": extra.get("occurred_at"),
                "last_seen_at": extra.get("last_seen_at"),
            }
        )
    if alert.alert_type == "ANIMAL_INTRUSION":
        extra = alert.extra or {}
        key_meta.update(
            {
                "animal_species": extra.get("animal_species"),
                "animal_count": extra.get("animal_count"),
                "animal_confidence": extra.get("animal_confidence"),
                "animal_is_night": extra.get("animal_is_night"),
                "snapshot_url": extra.get("snapshot_url"),
                "occurred_at": extra.get("occurred_at"),
                "last_seen_at": extra.get("last_seen_at"),
            }
        )
    if alert.alert_type == "FIRE_DETECTED":
        extra = alert.extra or {}
        key_meta.update(
            {
                "fire_classes": extra.get("fire_classes"),
                "fire_confidence": extra.get("fire_confidence"),
                "fire_model_name": extra.get("fire_model_name"),
                "fire_model_version": extra.get("fire_model_version"),
                "fire_weights_id": extra.get("fire_weights_id"),
                "snapshot_url": extra.get("snapshot_url"),
                "occurred_at": extra.get("occurred_at"),
                "last_seen_at": extra.get("last_seen_at"),
            }
        )
    if alert.alert_type == "DISPATCH_MOVEMENT_DELAY":
        extra = alert.extra or {}
        key_meta.update(
            {
                "plate_norm": extra.get("plate_norm"),
                "plate_raw": extra.get("plate_raw"),
                "entry_at": extra.get("entry_at"),
                "age_hours": extra.get("age_hours"),
                "threshold_hours": extra.get("threshold_hours"),
                "last_seen_at": extra.get("last_seen_at"),
                "snapshot_url": extra.get("snapshot_url"),
            }
        )
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


@router.get("/alerts/{alert_id}/deliveries", response_model=list[NotificationDeliveryOut])
def get_alert_deliveries(
    alert_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
    response: Response,
):
    page_size = clamp_page_size(page_size)
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if user and user.role.upper() == "GODOWN_MANAGER" and user.godown_id:
        if alert.godown_id != user.godown_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    base_query = (
        db.query(NotificationOutbox)
        .filter(NotificationOutbox.alert_id == alert.public_id)
    )
    total = base_query.count()
    deliveries = (
        base_query.order_by(NotificationOutbox.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    set_pagination_headers(response, total=total, page=page, page_size=page_size)
    return deliveries


@router.post("/alerts/{alert_id}/ack")
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db), user=Depends(get_optional_user)) -> dict:
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    actor = user.username if user else None
    action = AlertAction(alert_id=alert_id, action_type="ACK", actor=actor, note=None)
    alert.status = "ACK"
    if user and user.username:
        alert.acknowledged_by = user.username
    alert.acknowledged_at = datetime.utcnow()
    db.add(action)
    db.add(alert)
    db.commit()
    return {"status": alert.status, "alert_id": alert.id}


@router.get("/alerts/{alert_id}/actions", response_model=dict)
def list_alert_actions(
    alert_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
) -> dict:
    page_size = clamp_page_size(page_size)
    base_query = db.query(AlertAction).filter(AlertAction.alert_id == alert_id)
    total = base_query.count()
    actions = (
        base_query.order_by(AlertAction.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [AlertActionOut.model_validate(a).model_dump() for a in actions],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/alerts/{alert_id}/actions", response_model=AlertActionOut)
def create_alert_action(
    alert_id: int,
    payload: AlertActionCreate,
    db: Session = Depends(get_db),
) -> AlertActionOut:
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    action_type = payload.action_type.strip().upper()
    action = AlertAction(
        alert_id=alert_id,
        action_type=action_type,
        actor=payload.actor,
        note=payload.note,
    )
    if action_type in {"RESOLVE", "CLOSE", "CLOSED"}:
        alert.status = "CLOSED"
        alert.end_time = datetime.utcnow()
    elif action_type in {"REOPEN"}:
        alert.status = "OPEN"
        alert.end_time = None
    elif action_type in {"ACK"}:
        alert.status = "ACK"
        alert.acknowledged_by = payload.actor
        alert.acknowledged_at = datetime.utcnow()
    db.add(action)
    db.add(alert)
    db.commit()
    db.refresh(action)
    return AlertActionOut.model_validate(action)

@router.get("/alerts/{public_id}/ack-link", response_class=HTMLResponse)
def acknowledge_alert_via_link(
    public_id: str,
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Acknowledge an alert via one-time token embedded in WhatsApp/Email link."""
    alert = db.query(Alert).filter(Alert.public_id == public_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert.status == "ACK" or alert.acknowledged_at is not None:
        return HTMLResponse("<h3>✅ Alert already acknowledged</h3>", status_code=200)

    if alert.ack_token_used_at is not None:
        return HTMLResponse("<h3>✅ Link already used</h3>", status_code=200)

    now_utc = datetime.now(timezone.utc)
    if alert.ack_token_expires_at is not None and alert.ack_token_expires_at < now_utc:
        raise HTTPException(status_code=410, detail="Token expired")

    if not verify_raw_token(token, alert.ack_token_hash):
        raise HTTPException(status_code=401, detail="Invalid token")

    # Mark ACK + record action
    alert.status = "ACK"
    alert.acknowledged_by = "link"
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.ack_token_used_at = datetime.now(timezone.utc)

    action = AlertAction(alert_id=alert.id, action_type="ACK", actor="link", note="ack via link")
    db.add(action)
    db.add(alert)
    db.commit()

    return HTMLResponse(
        """<html><body style="font-family: Arial; padding: 20px;">
        <h2>✅ Alert acknowledged</h2>
        <p>You can close this page.</p>
        </body></html>""",
        status_code=200,
    )
