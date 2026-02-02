"""
DB-backed ANPR events endpoint.

Replaces CSV-based ANPR reads.
Dashboard should call: /api/v1/anpr/events
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from ...core.db import get_db
from ...models.anpr_event import AnprEvent
from ...models.anpr_vehicle import AnprVehicle

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


router = APIRouter(prefix="/api/v1/anpr", tags=["anpr"])


ANPR_EVENT_TYPES = (
    "ANPR_PLATE_VERIFIED",
    "ANPR_PLATE_ALERT",
    "ANPR_PLATE_DETECTED",
    "ANPR_TIME_VIOLATION",
)

LIST_TYPES = {"WHITELIST", "BLACKLIST"}


def _normalize_plate(text: str | None) -> str:
    return "".join(ch for ch in (text or "").upper() if ch.isalnum())


def _local_range_to_utc(tz_name: str, d1: date | None, d2: date | None):
    if not (d1 or d2):
        return None, None

    tz = ZoneInfo(tz_name) if ZoneInfo else timezone.utc

    def conv(d: date):
        return datetime.combine(d, time.min).replace(tzinfo=tz).astimezone(timezone.utc)

    start = conv(d1) if d1 else None
    end = conv(d2 + timedelta(days=1)) if d2 else None
    return start, end


def _meta(meta: Any, key: str):
    if not isinstance(meta, dict):
        return None
    v = meta.get(key)
    return str(v).strip() if v not in (None, "") else None


@router.get("/events")
def get_anpr_events(
    godown_id: str = Query(...),
    timezone_name: str = Query("Asia/Kolkata"),
    camera_id: Optional[str] = None,
    plate_text: Optional[str] = None,
    match_status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    start_utc, end_utc = _local_range_to_utc(timezone_name, date_from, date_to)

    filters = [
        AnprEvent.godown_id == godown_id,
        AnprEvent.event_type.in_(ANPR_EVENT_TYPES),
    ]
    if camera_id:
        filters.append(AnprEvent.camera_id == camera_id)
    if start_utc:
        filters.append(AnprEvent.timestamp_utc >= start_utc)
    if end_utc:
        filters.append(AnprEvent.timestamp_utc < end_utc)

    tz = ZoneInfo(timezone_name) if ZoneInfo else timezone.utc
    filters2 = list(filters)
    if plate_text:
        raw = plate_text.strip()
        if raw:
            filters2.append(
                (AnprEvent.plate_raw == raw) | (AnprEvent.plate_norm == "".join(ch for ch in raw.upper() if ch.isalnum()))
            )
    if match_status:
        filters2.append(AnprEvent.match_status == match_status.strip().upper())

    rows = (
        db.query(AnprEvent)
        .filter(and_(*filters2))
        .order_by(desc(AnprEvent.timestamp_utc))
        .limit(limit)
        .all()
    )

    plate_norms = {ev.plate_norm for ev in rows if ev.plate_norm}
    registry: dict[str, str] = {}
    if plate_norms:
        regs = (
            db.query(AnprVehicle.plate_norm, AnprVehicle.list_type)
            .filter(
                AnprVehicle.godown_id == godown_id,
                AnprVehicle.plate_norm.in_(plate_norms),
                AnprVehicle.is_active == True,  # noqa: E712
            )
            .all()
        )
        registry = {pn: (lt or "WHITELIST").upper() for pn, lt in regs}

    def _effective_status(ev: AnprEvent) -> str:
        status = (ev.match_status or "UNKNOWN").upper()
        pn = ev.plate_norm or _normalize_plate(ev.plate_raw)
        if status == "BLACKLIST":
            return "BLACKLIST"
        if status == "VERIFIED":
            return "VERIFIED"
        if pn and pn in registry:
            return "BLACKLIST" if registry[pn] == "BLACKLIST" else "VERIFIED"
        return status

    out = [
        {
            "timestamp_utc": ev.timestamp_utc.isoformat().replace("+00:00", "Z"),
            "timestamp_local": ev.timestamp_utc.astimezone(tz).replace(tzinfo=None).isoformat(sep=" "),
            "camera_id": ev.camera_id,
            "zone_id": ev.zone_id,
            "plate_text": (ev.plate_raw or ev.plate_norm or "").strip(),
            "match_status": _effective_status(ev),
            "event_type": ev.event_type,
            "confidence": float(ev.combined_conf or 0.0),
            "bbox": ev.bbox,
        }
        for ev in rows
        if (ev.plate_raw or ev.plate_norm)
    ]

    return {
        "source": {"db": True, "table": "anpr_events"},
        "count": len(out),
        "events": out,
    }
