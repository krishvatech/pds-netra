"""
Overview endpoint for the dashboard.

Aggregates counts and recent trends.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ...core.db import get_db
from ...models.godown import Godown, Camera
from ...models.event import Alert, Event


router = APIRouter(prefix="/api/v1", tags=["overview"])


def _status_for(open_critical: int, open_warning: int, cameras_offline: int) -> str:
    if open_critical > 0:
        return "CRITICAL"
    if open_warning > 0 or cameras_offline > 0:
        return "ISSUES"
    return "OK"


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    # Core counts
    godowns_monitored = db.query(func.count(Godown.id)).scalar() or 0
    open_alerts_critical = (
        db.query(func.count(Alert.id))
        .filter(Alert.status == "OPEN", Alert.severity_final == "critical")
        .scalar()
        or 0
    )
    open_alerts_warning = (
        db.query(func.count(Alert.id))
        .filter(Alert.status == "OPEN", Alert.severity_final == "warning")
        .scalar()
        or 0
    )

    # Alerts by type (open alerts)
    alerts_by_type: Dict[str, int] = {}
    rows = (
        db.query(Alert.alert_type, func.count(Alert.id))
        .filter(Alert.status == "OPEN")
        .group_by(Alert.alert_type)
        .all()
    )
    for alert_type, count in rows:
        alerts_by_type[alert_type] = int(count)

    # Alerts over time (last 7 days)
    since = datetime.utcnow() - timedelta(days=7)
    alerts = (
        db.query(Alert.start_time)
        .filter(Alert.start_time >= since)
        .all()
    )
    counts: Dict[str, int] = {}
    for (ts,) in alerts:
        key = ts.strftime("%b %d")
        counts[key] = counts.get(key, 0) + 1
    alerts_over_time = [{"t": k, "count": v} for k, v in sorted(counts.items())]

    # Godown summary cards
    godown_rows = db.query(Godown).order_by(Godown.id.asc()).all()
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
        },
        "godowns": godown_items,
    }
