"""Station monitoring alert endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.auth import UserContext, get_current_user
from ...core.db import get_db
from ...core.pagination import clamp_page_size
from ...models.event import Alert
from ...models.godown import Godown


router = APIRouter(prefix="/api/v1/station-monitoring", tags=["station-monitoring"])

ADMIN_ROLES = {"STATE_ADMIN", "HQ_ADMIN"}
ALERT_TYPE = "WORKPLACE_WORKSTATION_ABSENCE"


def _is_admin(user: UserContext) -> bool:
    return (user.role or "").upper() in ADMIN_ROLES


def _apply_scope(query, user: UserContext):
    if _is_admin(user):
        return query
    if not user.user_id:
        return query.filter(Alert.godown_id == "__forbidden__")
    return query.join(Godown, Godown.id == Alert.godown_id).filter(Godown.created_by_user_id == user.user_id)


@router.get("/alerts", response_model=dict)
def list_station_monitoring_alerts(
    godown_id: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    from_ts: Optional[datetime] = Query(None, alias="from"),
    to_ts: Optional[datetime] = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    page_size = clamp_page_size(page_size)
    query = db.query(Alert).filter(Alert.alert_type == ALERT_TYPE)
    query = _apply_scope(query, user)

    if godown_id:
        query = query.filter(Alert.godown_id == godown_id)
    if camera_id:
        query = query.filter(Alert.camera_id == camera_id)
    if zone_id:
        query = query.filter(Alert.zone_id == zone_id)
    if from_ts:
        query = query.filter(Alert.start_time >= from_ts)
    if to_ts:
        query = query.filter(Alert.start_time <= to_ts)

    total = query.count()
    alerts = (
        query.order_by(Alert.start_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for alert in alerts:
        extra = dict(alert.extra or {})
        snapshot_url = extra.get("snapshot_url")
        if not snapshot_url and alert.events:
            try:
                snapshot_url = alert.events[0].event.image_url
            except Exception:
                snapshot_url = None
        items.append(
            {
                "id": str(alert.id),
                "public_id": alert.public_id,
                "godown_id": alert.godown_id,
                "camera_id": alert.camera_id,
                "zone_id": alert.zone_id or extra.get("workstation_zone_id"),
                "alert_type": alert.alert_type,
                "severity_final": alert.severity_final,
                "status": alert.status,
                "start_time": alert.start_time,
                "created_at": alert.created_at,
                "summary": alert.summary,
                "snapshot_url": snapshot_url,
                "extra": extra,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
