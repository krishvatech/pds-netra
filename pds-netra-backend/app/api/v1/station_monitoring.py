"""Station monitoring alert and workstation config endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.auth import UserContext, get_current_user
from ...core.db import get_db
from ...core.pagination import clamp_page_size
from ...models.event import Alert
from ...models.godown import Camera, Godown
from ...services import station_workstations


router = APIRouter(prefix="/api/v1/station-monitoring", tags=["station-monitoring"])

ADMIN_ROLES = {"STATE_ADMIN", "HQ_ADMIN"}
ALERT_TYPE = "WORKPLACE_WORKSTATION_ABSENCE"


class WorkstationUpdatePayload(BaseModel):
    godown_id: str
    camera_id: str
    seat_label: Optional[str] = None
    employee_name: Optional[str] = None
    status: Optional[str] = None
    shift_start: Optional[str] = None
    shift_end: Optional[str] = None
    break_start: Optional[str] = None
    break_end: Optional[str] = None
    leave_from: Optional[str] = None
    leave_to: Optional[str] = None


def _normalize_status(raw: Optional[str]) -> str:
    value = (raw or "ACTIVE").strip().upper()
    if value not in {"ACTIVE", "ON_LEAVE", "DISABLED"}:
        raise HTTPException(status_code=422, detail="Invalid workstation status")
    return value


def _validate_workstation_payload(payload: WorkstationUpdatePayload) -> dict:
    status = _normalize_status(payload.status)
    shift_start = (payload.shift_start or "").strip() or None
    shift_end = (payload.shift_end or "").strip() or None
    break_start = (payload.break_start or "").strip() or None
    break_end = (payload.break_end or "").strip() or None
    leave_from = (payload.leave_from or "").strip() or None
    leave_to = (payload.leave_to or "").strip() or None

    if bool(shift_start) != bool(shift_end):
        raise HTTPException(status_code=422, detail="Shift start and shift end must both be set or both be empty")
    if bool(break_start) != bool(break_end):
        raise HTTPException(status_code=422, detail="Break start and break end must both be set or both be empty")
    if bool(leave_from) != bool(leave_to):
        raise HTTPException(status_code=422, detail="Leave from and leave to must both be set or both be empty")

    if break_start and break_end:
        try:
            datetime.strptime(break_start, "%H:%M")
            datetime.strptime(break_end, "%H:%M")
        except Exception:
            raise HTTPException(status_code=422, detail="Break start and break end must be in HH:MM format")

    if status == "ACTIVE":
        if leave_from or leave_to:
            raise HTTPException(status_code=422, detail="ACTIVE workstations cannot have a leave window")
    elif status == "ON_LEAVE":
        if not (leave_from and leave_to):
            raise HTTPException(status_code=422, detail="ON_LEAVE workstations require both leave from and leave to")
        if shift_start or shift_end or break_start or break_end:
            raise HTTPException(status_code=422, detail="ON_LEAVE workstations cannot have shift or break times")
        try:
            from_dt = datetime.fromisoformat(leave_from.replace("Z", "+00:00"))
            to_dt = datetime.fromisoformat(leave_to.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid leave window datetime format")
        if to_dt <= from_dt:
            raise HTTPException(status_code=422, detail="Leave to must be after leave from")
    elif status == "DISABLED":
        if shift_start or shift_end or break_start or break_end or leave_from or leave_to:
            raise HTTPException(status_code=422, detail="DISABLED workstations cannot have shift, break, or leave values")

    return {
        "status": status,
        "shift_start": shift_start,
        "shift_end": shift_end,
        "break_start": break_start,
        "break_end": break_end,
        "leave_from": leave_from,
        "leave_to": leave_to,
    }


def _is_admin(user: UserContext) -> bool:
    return (user.role or "").upper() in ADMIN_ROLES


def _apply_scope(query, user: UserContext):
    if _is_admin(user):
        return query
    if not user.user_id:
        return query.filter(Alert.godown_id == "__forbidden__")
    return query.join(Godown, Godown.id == Alert.godown_id).filter(Godown.created_by_user_id == user.user_id)


def _apply_camera_scope(query, user: UserContext):
    if _is_admin(user):
        return query
    if not user.user_id:
        return query.filter(Camera.godown_id == "__forbidden__")
    return query.join(Godown, Godown.id == Camera.godown_id).filter(Godown.created_by_user_id == user.user_id)


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


@router.get("/workstations", response_model=dict)
def list_workstations(
    godown_id: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    camera_query = _apply_camera_scope(db.query(Camera), user)
    if godown_id:
        camera_query = camera_query.filter(Camera.godown_id == godown_id)
    if camera_id:
        camera_query = camera_query.filter(Camera.id == camera_id)
    allowed = {(str(cam.godown_id), str(cam.id)) for cam in camera_query.all()}
    items = station_workstations.list_workstations(db, godown_id=godown_id, camera_id=camera_id)
    items = [item for item in items if (item["godown_id"], item["camera_id"]) in allowed]
    return {"items": items, "total": len(items)}


@router.patch("/workstations/{zone_id}", response_model=dict)
def update_workstation(
    zone_id: str,
    payload: WorkstationUpdatePayload,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    camera_query = _apply_camera_scope(db.query(Camera), user)
    camera = (
        camera_query
        .filter(Camera.godown_id == payload.godown_id, Camera.id == payload.camera_id)
        .first()
    )
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    if not station_workstations.is_monitored_workstation_zone(
        db,
        godown_id=payload.godown_id,
        camera_id=payload.camera_id,
        zone_id=zone_id,
    ):
        raise HTTPException(status_code=404, detail="Workstation zone is not selected in any enabled station monitoring rule")
    cleaned = _validate_workstation_payload(payload)
    workstation = station_workstations.upsert_workstation(
        godown_id=payload.godown_id,
        camera_id=payload.camera_id,
        zone_id=zone_id,
        seat_label=payload.seat_label,
        employee_name=payload.employee_name,
        status=cleaned["status"],
        shift_start=cleaned["shift_start"],
        shift_end=cleaned["shift_end"],
        break_start=cleaned["break_start"],
        break_end=cleaned["break_end"],
        leave_from=cleaned["leave_from"],
        leave_to=cleaned["leave_to"],
    )
    return workstation
