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
import os
from datetime import timedelta
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import select
from zoneinfo import ZoneInfo

from ..models.event import Event, Alert, AlertEventLink
from ..models.godown import Camera
from .after_hours import get_after_hours_policy, is_after_hours
from .notifications import notify_alert, notify_after_hours_alert, notify_animal_intrusion, notify_fire_detected


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
    if _handle_fire_detected(db, event):
        if updated_meta:
            db.add(event)
            db.commit()
        return
    if _handle_animal_intrusion(db, event):
        if updated_meta:
            db.add(event)
            db.commit()
        return
    alert_type = _map_event_to_alert_type(event.event_type, meta)
    if _handle_after_hours_presence(db, event):
        if updated_meta:
            db.add(event)
            db.commit()
        return
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
            notify_alert(db, alert, event)
        except Exception:
            pass


def _handle_after_hours_presence(db: Session, event: Event) -> bool:
    presence_types = {"PERSON_DETECTED", "VEHICLE_DETECTED", "ANPR_HIT"}
    if event.event_type not in presence_types:
        return False
    meta = event.meta or {}
    policy = get_after_hours_policy(db, event.godown_id)
    if not policy.enabled:
        return True
    is_ah = is_after_hours(event.timestamp_utc, policy)
    if meta.get("is_after_hours") != is_ah:
        meta = dict(meta)
        meta["is_after_hours"] = is_ah
        event.meta = meta
        db.add(event)
        db.commit()
    count_raw = meta.get("count")
    try:
        count = int(count_raw) if count_raw is not None else 0
    except Exception:
        count = 0
    if not is_ah or policy.presence_allowed or count <= 0:
        return True
    alert_type = (
        "AFTER_HOURS_PERSON_PRESENCE"
        if event.event_type == "PERSON_DETECTED"
        else "AFTER_HOURS_VEHICLE_PRESENCE"
    )
    snapshot_url = None
    if isinstance(meta.get("evidence"), dict):
        snapshot_url = meta.get("evidence", {}).get("snapshot_url")
    if not snapshot_url:
        snapshot_url = event.image_url
    plate = meta.get("vehicle_plate") or meta.get("plate_text")
    now = event.timestamp_utc
    existing = (
        db.query(Alert)
        .filter(
            Alert.godown_id == event.godown_id,
            Alert.camera_id == event.camera_id,
            Alert.alert_type == alert_type,
            Alert.status.in_(["OPEN", "ACK"]),
        )
        .order_by(Alert.start_time.desc())
        .first()
    )
    if existing:
        link = AlertEventLink(alert_id=existing.id, event_id=event.id)
        db.add(link)
        existing.end_time = now
        extra = dict(existing.extra or {})
        extra["last_seen_at"] = now.isoformat()
        extra["detected_count"] = count
        if snapshot_url:
            extra["snapshot_url"] = snapshot_url
        if plate:
            extra["vehicle_plate"] = plate
        existing.extra = extra
        db.commit()
        return True
    cutoff = now - timedelta(seconds=max(1, policy.cooldown_seconds))
    recent = (
        db.query(Alert)
        .filter(
            Alert.godown_id == event.godown_id,
            Alert.camera_id == event.camera_id,
            Alert.alert_type == alert_type,
            Alert.start_time >= cutoff,
        )
        .order_by(Alert.start_time.desc())
        .first()
    )
    if recent:
        return True
    summary = (
        f"After-hours person detected (count={count})"
        if alert_type == "AFTER_HOURS_PERSON_PRESENCE"
        else f"After-hours vehicle detected (count={count})"
    )
    alert = Alert(
        godown_id=event.godown_id,
        camera_id=event.camera_id,
        alert_type=alert_type,
        severity_final="critical",
        start_time=now,
        end_time=None,
        status="OPEN",
        title="After-hours Presence Detected",
        summary=summary,
        zone_id=(event.meta or {}).get("zone_id"),
        extra={
            "detected_count": count,
            "snapshot_url": snapshot_url,
            "vehicle_plate": plate,
            "occurred_at": now.isoformat(),
            "last_seen_at": now.isoformat(),
        },
    )
    db.add(alert)
    db.flush()
    link = AlertEventLink(alert_id=alert.id, event_id=event.id)
    db.add(link)
    db.commit()
    try:
        notify_after_hours_alert(db, alert, count=count, plate=plate, snapshot_url=snapshot_url)
    except Exception:
        pass
    return True


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
    if event_type == "ANIMAL_DETECTED":
        return "ANIMAL_INTRUSION"
    if event_type == "FIRE_DETECTED":
        return "FIRE_DETECTED"
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
        species = (event.meta or {}).get("animal_species") or (event.meta or {}).get("species")
        count = (event.meta or {}).get("animal_count") or (event.meta or {}).get("count")
        suffix = f" ({species})" if species else ""
        if count:
            return f"Animal intrusion detected{suffix} count={count}"
        return f"Animal intrusion detected in zone {event.meta.get('zone_id')}"
    if alert_type == "FIRE_DETECTED":
        conf = (event.meta or {}).get("fire_confidence") or (event.meta or {}).get("confidence")
        classes = (event.meta or {}).get("fire_classes")
        class_text = ""
        if isinstance(classes, list) and classes:
            class_text = f" ({', '.join(classes)})"
        if conf is not None:
            return f"Fire detected{class_text} confidence={float(conf):.2f}"
        return f"Fire detected{class_text}"
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


def _parse_time_string(value: str) -> datetime.time:
    try:
        return datetime.datetime.strptime(value, "%H:%M").time()
    except Exception:
        return datetime.time(0, 0)


def _is_time_in_range(now_time: datetime.time, start_time: datetime.time, end_time: datetime.time) -> bool:
    if start_time <= end_time:
        return start_time <= now_time < end_time
    return now_time >= start_time or now_time < end_time


def _is_night(ts: datetime.datetime) -> bool:
    tz_name = os.getenv("ANIMAL_TIMEZONE", "Asia/Kolkata")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    local_time = ts.astimezone(tz).timetz()
    start_t = _parse_time_string(os.getenv("ANIMAL_NIGHT_START", "19:00"))
    end_t = _parse_time_string(os.getenv("ANIMAL_NIGHT_END", "06:00"))
    return _is_time_in_range(local_time, start_t, end_t)


def _handle_fire_detected(db: Session, event: Event) -> bool:
    if event.event_type != "FIRE_DETECTED":
        return False
    meta = event.meta or {}
    classes = meta.get("fire_classes") or []
    confidence = meta.get("fire_confidence") or meta.get("confidence")
    model_name = meta.get("fire_model_name")
    model_version = meta.get("fire_model_version")
    weights_id = meta.get("fire_weights_id")
    cooldown_sec = int(os.getenv("FIRE_ALERT_COOLDOWN_SEC", "600"))

    event.severity_raw = "critical"
    db.add(event)
    db.commit()

    existing = (
        db.query(Alert)
        .filter(
            Alert.godown_id == event.godown_id,
            Alert.camera_id == event.camera_id,
            Alert.alert_type == "FIRE_DETECTED",
            Alert.status.in_(["OPEN", "ACK"]),
        )
        .order_by(Alert.start_time.desc())
        .first()
    )
    if existing:
        link = AlertEventLink(alert_id=existing.id, event_id=event.id)
        db.add(link)
        existing.end_time = event.timestamp_utc
        extra = dict(existing.extra or {})
        extra["fire_classes"] = classes
        extra["fire_confidence"] = confidence
        extra["fire_model_name"] = model_name
        extra["fire_model_version"] = model_version
        extra["fire_weights_id"] = weights_id
        extra["last_seen_at"] = event.timestamp_utc.isoformat()
        if event.image_url:
            extra["snapshot_url"] = event.image_url
        existing.extra = extra
        db.commit()
        return True

    cutoff = event.timestamp_utc - timedelta(seconds=max(1, cooldown_sec))
    recent = (
        db.query(Alert)
        .filter(
            Alert.godown_id == event.godown_id,
            Alert.camera_id == event.camera_id,
            Alert.alert_type == "FIRE_DETECTED",
            Alert.start_time >= cutoff,
        )
        .order_by(Alert.start_time.desc())
        .first()
    )
    if recent:
        return True

    alert = Alert(
        godown_id=event.godown_id,
        camera_id=event.camera_id,
        alert_type="FIRE_DETECTED",
        severity_final="critical",
        start_time=event.timestamp_utc,
        end_time=None,
        status="OPEN",
        summary=_build_alert_summary("FIRE_DETECTED", event),
        zone_id=(event.meta or {}).get("zone_id"),
        extra={
            "fire_classes": classes,
            "fire_confidence": confidence,
            "fire_model_name": model_name,
            "fire_model_version": model_version,
            "fire_weights_id": weights_id,
            "snapshot_url": event.image_url,
            "occurred_at": event.timestamp_utc.isoformat(),
            "last_seen_at": event.timestamp_utc.isoformat(),
        },
    )
    db.add(alert)
    db.flush()
    link = AlertEventLink(alert_id=alert.id, event_id=event.id)
    db.add(link)
    db.commit()
    try:
        notify_fire_detected(
            db,
            alert,
            classes=classes,
            confidence=confidence,
            snapshot_url=event.image_url,
        )
    except Exception:
        pass
    return True


def _handle_animal_intrusion(db: Session, event: Event) -> bool:
    if event.event_type not in {"ANIMAL_INTRUSION", "ANIMAL_DETECTED"}:
        return False
    meta = event.meta or {}
    species = meta.get("animal_species") or meta.get("species") or meta.get("movement_type")
    count_raw = meta.get("animal_count") or meta.get("count")
    try:
        count = int(count_raw) if count_raw is not None else 1
    except Exception:
        count = 1
    confidence = meta.get("animal_confidence") or meta.get("confidence")
    is_night = _is_night(event.timestamp_utc)
    if meta.get("animal_is_night") != is_night:
        meta = dict(meta)
        meta["animal_is_night"] = is_night
        event.meta = meta
        db.add(event)
        db.commit()
    cooldown_sec = int(os.getenv("ANIMAL_ALERT_COOLDOWN_SEC", "300"))
    severity_day = os.getenv("ANIMAL_DAY_SEVERITY", "warning").lower()
    severity = "critical" if is_night else severity_day
    event.severity_raw = severity
    db.add(event)
    db.commit()
    species_key = species or "unknown"

    def _alert_species(alert: Alert) -> str:
        extra = alert.extra or {}
        if isinstance(extra, dict):
            return extra.get("animal_species") or "unknown"
        return "unknown"

    existing = (
        db.query(Alert)
        .filter(
            Alert.godown_id == event.godown_id,
            Alert.camera_id == event.camera_id,
            Alert.alert_type == "ANIMAL_INTRUSION",
            Alert.status.in_(["OPEN", "ACK"]),
        )
        .order_by(Alert.start_time.desc())
        .first()
    )
    if existing and _alert_species(existing) != species_key:
        existing = None
    if existing:
        link = AlertEventLink(alert_id=existing.id, event_id=event.id)
        db.add(link)
        existing.end_time = event.timestamp_utc
        extra = dict(existing.extra or {})
        extra["animal_species"] = species_key
        extra["animal_count"] = count
        extra["animal_confidence"] = confidence
        extra["animal_is_night"] = is_night
        extra["last_seen_at"] = event.timestamp_utc.isoformat()
        if event.image_url:
            extra["snapshot_url"] = event.image_url
        existing.extra = extra
        db.commit()
        return True
    cutoff = event.timestamp_utc - timedelta(seconds=max(1, cooldown_sec))
    recent_alerts = (
        db.query(Alert)
        .filter(
            Alert.godown_id == event.godown_id,
            Alert.camera_id == event.camera_id,
            Alert.alert_type == "ANIMAL_INTRUSION",
            Alert.start_time >= cutoff,
        )
        .order_by(Alert.start_time.desc())
        .all()
    )
    if any(_alert_species(alert) == species_key for alert in recent_alerts):
        return True
    alert = Alert(
        godown_id=event.godown_id,
        camera_id=event.camera_id,
        alert_type="ANIMAL_INTRUSION",
        severity_final=severity,
        start_time=event.timestamp_utc,
        end_time=None,
        status="OPEN",
        summary=_build_alert_summary("ANIMAL_INTRUSION", event),
        zone_id=meta.get("zone_id"),
        extra={
            "animal_species": species_key,
            "animal_count": count,
            "animal_confidence": confidence,
            "animal_is_night": is_night,
            "snapshot_url": event.image_url,
            "occurred_at": event.timestamp_utc.isoformat(),
            "last_seen_at": event.timestamp_utc.isoformat(),
        },
    )
    db.add(alert)
    db.flush()
    link = AlertEventLink(alert_id=alert.id, event_id=event.id)
    db.add(link)
    db.commit()
    try:
        notify_animal_intrusion(db, alert, species=species_key, count=count, snapshot_url=event.image_url, is_night=is_night)
    except Exception:
        pass
    return True
