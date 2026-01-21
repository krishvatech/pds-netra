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
from datetime import timedelta
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import select

from ..models.event import Event, Alert, AlertEventLink


def apply_rules(db: Session, event: Event) -> None:
    """
    Apply central rules to a newly inserted raw event.

    Depending on the event type, this function either creates a new
    alert or associates the event with an existing open alert. Alerts
    group multiple related events and manage their lifecycle.
    """
    # Map raw event_type to alert_type. Unknown types result in no alert.
    alert_type = _map_event_to_alert_type(event.event_type, event.meta)
    if alert_type is None:
        return
    # Determine zone_id from meta if available
    zone_id = None
    if event.meta:
        zone_id = event.meta.get("zone_id")
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


def _map_event_to_alert_type(event_type: str, meta: dict | None) -> Optional[str]:
    """Map a raw event_type to a higher-level alert_type."""
    if event_type in {"UNAUTH_PERSON", "LOITERING"}:
        return "SECURITY_UNAUTH_ACCESS"
    if event_type == "ANIMAL_INTRUSION":
        return "ANIMAL_INTRUSION"
    if event_type == "BAG_MOVEMENT":
        # Only consider after-hours or generic bag movements as anomalies
        movement_type = meta.get("movement_type") if meta else None
        if movement_type == "AFTER_HOURS":
            return "OPERATION_BAG_MOVEMENT_ANOMALY"
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
        return f"Unauthorized access detected in zone {event.meta.get('zone_id')} at {event.timestamp_utc}" if event.meta else "Unauthorized access detected"
    if alert_type == "ANIMAL_INTRUSION":
        return f"Animal intrusion detected in zone {event.meta.get('zone_id')}"
    if alert_type == "OPERATION_BAG_MOVEMENT_ANOMALY":
        return f"After-hours bag movement detected in zone {event.meta.get('zone_id')}"
    if alert_type == "CAMERA_HEALTH_ISSUE":
        reason = event.meta.get("reason") if event.meta else None
        return f"Camera health issue: {reason}"
    if alert_type == "ANPR_MISMATCH_VEHICLE":
        plate = event.meta.get("plate_text") if event.meta else None
        return f"ANPR mismatch for plate {plate}"
    return f"Alert: {alert_type}"