from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from ...core.db import get_db
from ...models.vehicle_gate_session import VehicleGateSession
from ...services.vehicle_gate import _ensure_utc

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


router = APIRouter(prefix="/api/v1/anpr", tags=["anpr"])


@router.get("/sessions")
def anpr_sessions(
    godown_id: str = Query(...),
    timezone_name: str = Query("Asia/Kolkata"),
    status: Optional[str] = Query(None, description="OPEN/CLOSED"),
    camera_id: Optional[str] = Query(None),
    plate_text: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    tz = ZoneInfo(timezone_name) if ZoneInfo else datetime.timezone.utc

    filters = [VehicleGateSession.godown_id == godown_id]
    if status:
        filters.append(VehicleGateSession.status == status.strip().upper())
    if camera_id:
        filters.append(VehicleGateSession.anpr_camera_id == camera_id)
    if plate_text:
        norm = "".join(ch for ch in plate_text.strip().upper() if ch.isalnum())
        if norm:
            filters.append(VehicleGateSession.plate_norm == norm)

    sessions = (
        db.query(VehicleGateSession)
        .filter(and_(*filters))
        .order_by(desc(VehicleGateSession.last_seen_at))
        .limit(limit)
        .all()
    )

    out = []
    for s in sessions:
        entry_at = _ensure_utc(s.entry_at)
        exit_at = _ensure_utc(s.exit_at) if s.exit_at else None
        last_seen = _ensure_utc(s.last_seen_at)

        out.append(
            {
                "id": s.id,
                "godown_id": s.godown_id,
                "camera_id": s.anpr_camera_id,
                "plate_text": s.plate_raw,
                "plate_norm": s.plate_norm,
                "entry_at_utc": entry_at.isoformat().replace("+00:00", "Z"),
                "last_seen_utc": last_seen.isoformat().replace("+00:00", "Z"),
                "exit_at_utc": exit_at.isoformat().replace("+00:00", "Z") if exit_at else None,
                "entry_time_local": entry_at.astimezone(tz).replace(tzinfo=None).isoformat(sep=" "),
                "exit_time_local": exit_at.astimezone(tz).replace(tzinfo=None).isoformat(sep=" ") if exit_at else None,
                "duration_seconds": int((exit_at - entry_at).total_seconds()) if exit_at else None,
                "session_status": "ACTIVE" if (s.status or "").upper() == "OPEN" else "CLOSED",
                "reminders_sent": s.reminders_sent or {},
                "last_snapshot_url": s.last_snapshot_url,
            }
        )

    return {"sessions": out}
