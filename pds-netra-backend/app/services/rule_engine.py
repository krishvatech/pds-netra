"""
Central rule engine for PDS Netra backend.

This module contains logic to interpret raw events and generate higher-level
alerts. Alerts aggregate related events over time windows and apply
central policies such as severity escalation, notification thresholds,
and correlation with dispatch plans. The initial implementation here
provides a minimal working rule set based on event type and recent
history.
"""

from __future__ import annotations

import datetime
import json
from datetime import timedelta
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import select

from ..models.event import Event, Alert, AlertEventLink
from ..models.godown import Camera
from .notifications import notify_alert


def _parse_bbox(bbox_raw: str | None) -> Optional[list[int]]:
    if not bbox_raw:
        return None
    try:
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
    camera = db.get(Camera, event.camera_id)
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


def apply_rules(db: Session, event: Event) -> None:
    """
    Apply central rules to a newly inserted raw event.

    Depending on the event type, this function either creates a new
    alert or associates the event with an existing open alert. Alerts
    group multiple related events and manage their lifecycle.
    """
    # Ensure zone_id is populated when possible (helps zone-aware alerts).
    meta = event.meta or {}
    zone_id = meta.get("zone_id")
    updated_meta = False
    if not zone_id:
        inferred_zone = _infer_zone_id(db, event)
        if inferred_zone:
            meta = dict(meta)
            meta["zone_id"] = inferred_zone
            event.meta = meta
            updated_meta = True
            zone_id = inferred_zone
    # Map raw event_type to alert_type. Unknown types result in no alert.
    alert_type = _map_event_to_alert_type(event.event_type, meta)
    if alert_type is None:
        if updated_meta:
            db.add(event)
            db.commit()
        return
    # Determine zone_id from meta if available
    if zone_id is None and event.meta:
        zone_id = event.meta.get("zone_id")
    if not zone_id:
        rule_id = (event.meta or {}).get("rule_id")
        if rule_id in {"TEST_CLASS_DETECT", "TEST_PERSON_DETECT"}:
            return
    # Determine severity: for now propagate raw severity
    severity_final = event.severity_raw
    # Find existing open alert within the last 10 minutes for the same godown, alert_type and zone
    now = event.timestamp_utc
    cutoff = now - timedelta(minutes=10)
    stmt = select(Alert).where(
        Alert.godown_id == event.godown_id,
        Alert.alert_type == alert_type,
        Alert.status == "OPEN",
        Alert.start_time >= cutoff,
    )
    if zone_id:
        stmt = stmt.where(Alert.zone_id == zone_id)
    existing_alert: Optional[Alert] = db.execute(stmt).scalars().first()
    if existing_alert:
        # Attach event to existing alert and update end_time
        link = AlertEventLink(alert_id=existing_alert.id, event_id=event.id)
        db.add(link)
        existing_alert.end_time = event.timestamp_utc
        # Optionally adjust severity if event severity is higher
        if _severity_rank(severity_final) > _severity_rank(existing_alert.severity_final):
            existing_alert.severity_final = severity_final
        db.commit()
    else:
        # Create new alert
        alert = Alert(
            godown_id=event.godown_id,
            camera_id=event.camera_id,
            alert_type=alert_type,
            severity_final=severity_final,
            start_time=event.timestamp_utc,
            end_time=None,
            status="OPEN",
            summary=_build_alert_summary(alert_type, event),
            zone_id=zone_id,
            extra=None,
        )
        db.add(alert)
        db.flush()  # to get alert.id
        link = AlertEventLink(alert_id=alert.id, event_id=event.id)
        db.add(link)
        db.commit()
        try:
            notify_alert(alert, event)
        except Exception:
            pass


def _map_event_to_alert_type(event_type: str, meta: dict | None) -> Optional[str]:
    """Map a raw event_type to a higher-level alert_type."""
    if event_type in {"UNAUTH_PERSON", "LOITERING", "FACE_UNKNOWN_ACCESS"}:
        movement = (meta or {}).get("movement_type")
        if movement:
            movement_norm = str(movement).strip().lower()
            animal_classes = {
                "cat",
                "dog",
                "cow",
                "buffalo",
                "deer",
                "donkey",
                "cheetah",
                "leopard",
                "lion",
                "tiger",
            }
            if movement_norm in animal_classes:
                return "ANIMAL_INTRUSION"
            if movement_norm == "vehicle":
                return "ANPR_MISMATCH_VEHICLE"
        return "SECURITY_UNAUTH_ACCESS"
    if event_type == "ANIMAL_INTRUSION":
        return "ANIMAL_INTRUSION"
    if event_type == "BAG_MOVEMENT":
        # Only consider after-hours or generic bag movements as anomalies
        movement_type = meta.get("movement_type") if meta else None
        if movement_type == "AFTER_HOURS":
            return "OPERATION_BAG_MOVEMENT_ANOMALY"
        if movement_type == "UNPLANNED":
            return "OPERATION_UNPLANNED_MOVEMENT"
        # For GENERIC bag movements we may not create alerts yet
        return None
    if event_type in {"CAMERA_TAMPERED", "CAMERA_OFFLINE", "LOW_LIGHT"}:
        return "CAMERA_HEALTH_ISSUE"
    if event_type == "ANPR_PLATE_MISMATCH":
        return "ANPR_MISMATCH_VEHICLE"
    # ANPR_PLATE_DETECTED events are informational only
    return None


def _severity_rank(sev: str) -> int:
    """Return a numeric ranking for severity strings."""
    ranks = {"info": 1, "warning": 2, "critical": 3}
    return ranks.get(sev.lower(), 1)


def _build_alert_summary(alert_type: str, event: Event) -> str:
    """Generate a human-readable summary for a new alert."""
    if alert_type == "SECURITY_UNAUTH_ACCESS":
        movement = event.meta.get("movement_type") if event.meta else None
        zone = event.meta.get("zone_id") if event.meta else None
        if movement:
            return f"Detected {movement} in zone {zone or 'unknown'} at {event.timestamp_utc}"
        return (
            f"Unauthorized access detected in zone {zone} at {event.timestamp_utc}"
            if zone
            else "Unauthorized access detected"
        )
    if alert_type == "ANIMAL_INTRUSION":
        return f"Animal intrusion detected in zone {event.meta.get('zone_id')}"
    if alert_type == "OPERATION_BAG_MOVEMENT_ANOMALY":
        return f"After-hours bag movement detected in zone {event.meta.get('zone_id')}"
    if alert_type == "OPERATION_UNPLANNED_MOVEMENT":
        zone = event.meta.get("zone_id") if event.meta else None
        plan_id = None
        extra = event.meta.get("extra") if event.meta else None
        if isinstance(extra, dict):
            plan_id = extra.get("plan_id")
        if plan_id:
            return f"Unplanned bag movement detected in zone {zone} (plan {plan_id})"
        return (
            f"Unplanned bag movement detected in zone {zone}"
            if zone
            else "Unplanned bag movement detected"
        )
    if alert_type == "CAMERA_HEALTH_ISSUE":
        reason = event.meta.get("reason") if event.meta else None
        return f"Camera health issue: {reason}"
    if alert_type == "ANPR_MISMATCH_VEHICLE":
        plate = event.meta.get("plate_text") if event.meta else None
        return f"ANPR mismatch for plate {plate}"
    return f"Alert: {alert_type}"
