"""
Overview endpoint for the dashboard.

Aggregates counts and recent trends.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from ...core.db import get_db
from ...core.auth import UserContext, get_current_user
from ...models.godown import Godown, Camera
from ...models.event import Alert, Event
from ...models.vehicle_gate_session import VehicleGateSession
from ...core.pagination import clamp_page_size


router = APIRouter(prefix="/api/v1", tags=["overview"])
ADMIN_ROLES = {"STATE_ADMIN", "HQ_ADMIN"}


def _is_admin(user: UserContext) -> bool:
    return (user.role or "").upper() in ADMIN_ROLES


def _status_for(open_critical: int, open_warning: int, cameras_offline: int) -> str:
    if open_critical > 0:
        return "CRITICAL"
    if open_warning > 0 or cameras_offline > 0:
        return "ISSUES"
    return "OK"


@router.get("/overview")
def overview(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    page_size = clamp_page_size(page_size)
    allowed_godowns = db.query(Godown.id)
    if not _is_admin(user):
        if not user.user_id:
            allowed_godowns = allowed_godowns.filter(Godown.id == "__forbidden__")
        else:
            allowed_godowns = allowed_godowns.filter(Godown.created_by_user_id == user.user_id)

    allowed_ids_select = allowed_godowns.with_entities(Godown.id)

    # Core counts
    godowns_monitored = db.query(func.count(Godown.id)).filter(Godown.id.in_(allowed_ids_select)).scalar() or 0
    open_alerts_critical = (
        db.query(func.count(Alert.id))
        .filter(Alert.status == "OPEN", Alert.severity_final == "critical", Alert.godown_id.in_(allowed_ids_select))
        .scalar()
        or 0
    )
    open_alerts_warning = (
        db.query(func.count(Alert.id))
        .filter(Alert.status == "OPEN", Alert.severity_final == "warning", Alert.godown_id.in_(allowed_ids_select))
        .scalar()
        or 0
    )
    open_gate_sessions = (
        db.query(func.count(VehicleGateSession.id))
        .filter(VehicleGateSession.status == "OPEN", VehicleGateSession.godown_id.in_(allowed_ids_select))
        .scalar()
        or 0
    )

    # Alerts by type (open alerts)
    alerts_by_type: Dict[str, int] = {}
    rows = (
        db.query(Alert.alert_type, func.count(Alert.id))
        .filter(Alert.status == "OPEN", Alert.godown_id.in_(allowed_ids_select))
        .group_by(Alert.alert_type)
        .all()
    )
    for alert_type, count in rows:
        alerts_by_type[alert_type] = int(count)

    # Alerts over time (last 7 days)
    since = datetime.utcnow() - timedelta(days=7)
    alerts = (
        db.query(Alert.start_time)
        .filter(Alert.start_time >= since, Alert.godown_id.in_(allowed_ids_select))
        .all()
    )
    counts: Dict[str, int] = {}
    for (ts,) in alerts:
        key = ts.strftime("%b %d")
        counts[key] = counts.get(key, 0) + 1
    alerts_over_time = [{"t": k, "count": v} for k, v in sorted(counts.items())]

    now = datetime.utcnow()
    since_24h = now - timedelta(hours=24)
    after_hours_person_24h = (
        db.query(func.count(Alert.id))
        .filter(
            Alert.alert_type == "AFTER_HOURS_PERSON_PRESENCE",
            Alert.start_time >= since_24h,
            Alert.godown_id.in_(allowed_ids_select),
        )
        .scalar()
        or 0
    )
    after_hours_vehicle_24h = (
        db.query(func.count(Alert.id))
        .filter(
            Alert.alert_type == "AFTER_HOURS_VEHICLE_PRESENCE",
            Alert.start_time >= since_24h,
            Alert.godown_id.in_(allowed_ids_select),
        )
        .scalar()
        or 0
    )
    after_hours_person_7d = (
        db.query(func.count(Alert.id))
        .filter(
            Alert.alert_type == "AFTER_HOURS_PERSON_PRESENCE",
            Alert.start_time >= since,
            Alert.godown_id.in_(allowed_ids_select),
        )
        .scalar()
        or 0
    )
    after_hours_vehicle_7d = (
        db.query(func.count(Alert.id))
        .filter(
            Alert.alert_type == "AFTER_HOURS_VEHICLE_PRESENCE",
            Alert.start_time >= since,
            Alert.godown_id.in_(allowed_ids_select),
        )
        .scalar()
        or 0
    )

    animal_intrusions_24h = (
        db.query(func.count(Alert.id))
        .filter(
            Alert.alert_type == "ANIMAL_INTRUSION",
            Alert.start_time >= since_24h,
            Alert.godown_id.in_(allowed_ids_select),
        )
        .scalar()
        or 0
    )
    animal_intrusions_7d = (
        db.query(func.count(Alert.id))
        .filter(
            Alert.alert_type == "ANIMAL_INTRUSION",
            Alert.start_time >= since,
            Alert.godown_id.in_(allowed_ids_select),
        )
        .scalar()
        or 0
    )
    fire_alerts_24h = (
        db.query(func.count(Alert.id))
        .filter(
            Alert.alert_type == "FIRE_DETECTED",
            Alert.start_time >= since_24h,
            Alert.godown_id.in_(allowed_ids_select),
        )
        .scalar()
        or 0
    )
    fire_alerts_7d = (
        db.query(func.count(Alert.id))
        .filter(
            Alert.alert_type == "FIRE_DETECTED",
            Alert.start_time >= since,
            Alert.godown_id.in_(allowed_ids_select),
        )
        .scalar()
        or 0
    )

    # Godown summary cards
    godown_rows = (
        db.query(Godown)
        .filter(Godown.id.in_(allowed_ids_select))
        .order_by(Godown.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    godown_items: List[dict] = []
    for g in godown_rows:
        cameras_total = db.query(func.count(Camera.id)).filter(Camera.godown_id == g.id).scalar() or 0
        open_critical = (
            db.query(func.count(Alert.id))
            .filter(
                Alert.godown_id == g.id,
                Alert.status == "OPEN",
                Alert.severity_final == "critical",
            )
            .scalar()
            or 0
        )
        open_warning = (
            db.query(func.count(Alert.id))
            .filter(
                Alert.godown_id == g.id,
                Alert.status == "OPEN",
                Alert.severity_final == "warning",
            )
            .scalar()
            or 0
        )
        last_event = (
            db.query(Event.timestamp_utc)
            .filter(Event.godown_id == g.id)
            .order_by(Event.timestamp_utc.desc())
            .first()
        )
        cameras_offline = 0
        godown_items.append(
            {
                "godown_id": g.id,
                "name": g.name,
                "district": g.district,
                "capacity": None,
                "cameras_total": cameras_total,
                "cameras_offline": cameras_offline,
                "open_alerts_warning": open_warning,
                "open_alerts_critical": open_critical,
                "last_event_time_utc": last_event[0] if last_event else None,
                "status": _status_for(open_critical, open_warning, cameras_offline),
            }
        )

    return {
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "stats": {
            "godowns_monitored": godowns_monitored,
            "open_alerts_critical": open_alerts_critical,
            "open_alerts_warning": open_alerts_warning,
            "cameras_with_issues": 0,
            "alerts_by_type": alerts_by_type,
            "alerts_over_time": alerts_over_time,
            "after_hours_person_24h": after_hours_person_24h,
            "after_hours_vehicle_24h": after_hours_vehicle_24h,
            "after_hours_person_7d": after_hours_person_7d,
            "after_hours_vehicle_7d": after_hours_vehicle_7d,
            "animal_intrusions_24h": animal_intrusions_24h,
            "animal_intrusions_7d": animal_intrusions_7d,
            "fire_alerts_24h": fire_alerts_24h,
            "fire_alerts_7d": fire_alerts_7d,
            "open_gate_sessions": open_gate_sessions,
        },
        "godowns": godown_items,
        "page": page,
        "page_size": page_size,
        "total_godowns": godowns_monitored,
    }
