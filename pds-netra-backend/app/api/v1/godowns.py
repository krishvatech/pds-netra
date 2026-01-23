"""
Godown endpoints for PDS Netra backend.

Provides list and detail views used by the dashboard.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from ...core.db import get_db
from ...models.godown import Godown, Camera
from ...models.event import Alert, Event


router = APIRouter(prefix="/api/v1/godowns", tags=["godowns"])


def _status_for(open_critical: int, open_warning: int, cameras_offline: int) -> str:
    if open_critical > 0:
        return "CRITICAL"
    if open_warning > 0 or cameras_offline > 0:
        return "ISSUES"
    return "OK"


@router.get("")
def list_godowns(
    district: str | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
) -> List[dict]:
    query = db.query(Godown)
    if district:
        query = query.filter(Godown.district == district)
    godowns = query.order_by(Godown.id.asc()).all()
    results: List[dict] = []
    for g in godowns:
        cameras_total = db.query(func.count(Camera.id)).filter(Camera.godown_id == g.id).scalar() or 0
        # Alerts counts
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
        status_val = _status_for(open_critical, open_warning, cameras_offline)
        if status and status_val != status:
            continue
        results.append(
            {
                "godown_id": g.id,
                "name": g.name,
                "district": g.district,
                "capacity": None,
                "cameras_total": cameras_total,
                "cameras_online": cameras_total - cameras_offline,
                "cameras_offline": cameras_offline,
                "open_alerts_total": open_critical + open_warning,
                "open_alerts_warning": open_warning,
                "open_alerts_critical": open_critical,
                "last_event_time_utc": last_event[0] if last_event else None,
                "status": status_val,
            }
        )
    return results


@router.get("/{godown_id}")
def get_godown_detail(godown_id: str, db: Session = Depends(get_db)) -> dict:
    godown = db.get(Godown, godown_id)
    if not godown:
        raise HTTPException(status_code=404, detail="Godown not found")
    cameras = (
        db.query(Camera)
        .filter(Camera.godown_id == godown_id)
        .order_by(Camera.id.asc())
        .all()
    )
    # Simple 24h summary
    since = datetime.utcnow() - timedelta(hours=24)
    alerts_last_24h = (
        db.query(func.count(Alert.id))
        .filter(Alert.godown_id == godown_id, Alert.start_time >= since)
        .scalar()
        or 0
    )
    critical_last_24h = (
        db.query(func.count(Alert.id))
        .filter(
            Alert.godown_id == godown_id,
            Alert.start_time >= since,
            Alert.severity_final == "critical",
        )
        .scalar()
        or 0
    )
    last_event = (
        db.query(Event.timestamp_utc)
        .filter(Event.godown_id == godown_id)
        .order_by(Event.timestamp_utc.desc())
        .first()
    )
    return {
        "godown_id": godown.id,
        "name": godown.name,
        "district": godown.district,
        "capacity": None,
        "cameras": [
            {"camera_id": c.id, "label": c.label, "role": c.role, "zones_json": c.zones_json} for c in cameras
        ],
        "summary": {
            "alerts_last_24h": alerts_last_24h,
            "critical_alerts_last_24h": critical_last_24h,
            "last_event_time_utc": last_event[0] if last_event else None,
        },
    }
