"""
API endpoints for vehicle gate sessions.
"""

from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from ...core.db import get_db
from ...core.auth import get_optional_user
from ...models.vehicle_gate_session import VehicleGateSession
from ...services.vehicle_gate import compute_next_threshold, _ensure_utc


router = APIRouter(prefix="/api/v1/vehicle-gate-sessions", tags=["vehicle-gate-sessions"])


def _parse_dt(value: Optional[str]) -> Optional[datetime.datetime]:
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


@router.get("")
def list_vehicle_gate_sessions(
    status: Optional[str] = Query(default=None),
    godown_id: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
) -> dict:
    query = db.query(VehicleGateSession)
    if user and user.role.upper() == "GODOWN_MANAGER" and user.godown_id:
        if godown_id and godown_id != user.godown_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        godown_id = user.godown_id
    if status:
        query = query.filter(VehicleGateSession.status == status)
    if godown_id:
        query = query.filter(VehicleGateSession.godown_id == godown_id)
    if q:
        term = q.strip().upper()
        query = query.filter(
            func.upper(VehicleGateSession.plate_norm).like(f"%{term}%")
            | func.upper(VehicleGateSession.plate_raw).like(f"%{term}%")
        )
    start_dt = _parse_dt(date_from)
    end_dt = _parse_dt(date_to)
    if start_dt:
        query = query.filter(VehicleGateSession.entry_at >= start_dt)
    if end_dt:
        query = query.filter(VehicleGateSession.entry_at <= end_dt)

    total = query.count()
    items = (
        query.order_by(VehicleGateSession.entry_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    out = []
    for session in items:
        entry_at = _ensure_utc(session.entry_at)
        age_hours = max(0.0, (now - entry_at).total_seconds() / 3600.0)
        out.append(
            {
                "id": session.id,
                "godown_id": session.godown_id,
                "anpr_camera_id": session.anpr_camera_id,
                "plate_raw": session.plate_raw,
                "plate_norm": session.plate_norm,
                "entry_at": session.entry_at,
                "exit_at": session.exit_at,
                "status": session.status,
                "last_seen_at": session.last_seen_at,
                "reminders_sent": session.reminders_sent or {},
                "last_snapshot_url": session.last_snapshot_url,
                "age_hours": round(age_hours, 2) if session.status == "OPEN" else None,
                "next_threshold_hours": compute_next_threshold(session.reminders_sent),
            }
        )
    return {"items": out, "total": total, "page": page, "page_size": page_size}
