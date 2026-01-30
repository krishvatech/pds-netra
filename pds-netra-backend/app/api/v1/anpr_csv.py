"""CSV-first ANPR endpoints.

This backend has a full DB-backed event/alert pipeline via MQTT.
However, for the ANPR PoC you requested (JSON whitelist + CSV events),
we expose a lightweight endpoint that reads ANPR event rows from CSV
written by the edge node.

Folder convention (default):
  <backend-root>/data/anpr_csv/<GODOWN_ID>/*.csv

The edge can be configured to write its ANPR CSV to that folder.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from ...core.config import settings

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


router = APIRouter(prefix="/api/v1/anpr", tags=["anpr"])


@dataclass
class _CsvEvent:
    timestamp_utc: datetime
    camera_id: str
    zone_id: Optional[str]
    plate_text: str
    det_conf: float
    ocr_conf: float
    combined_conf: float
    match_status: str
    bbox: Optional[list[int]]


def _backend_root() -> Path:
    # .../backend/app/api/v1/anpr_csv.py -> parents[3] == backend/
    return Path(__file__).resolve().parents[3]


def _resolve_csv_dir() -> Path:
    base = Path(settings.anpr_csv_dir)
    if not base.is_absolute():
        base = (_backend_root() / base).resolve()
    return base


def _safe_join(base: Path, *parts: str) -> Path:
    # Prevent path traversal
    out = (base.joinpath(*parts)).resolve()
    try:
        out.relative_to(base)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path")
    return out


def _parse_bbox(bbox_raw: str | None) -> Optional[list[int]]:
    if not bbox_raw:
        return None
    s = bbox_raw.strip()
    if not (s.startswith("[") and s.endswith("]")):
        return None
    try:
        parts = s.strip("[]").split(",")
        vals = [int(float(p.strip())) for p in parts if p.strip()]
        return vals if len(vals) == 4 else None
    except Exception:
        return None


def _parse_ts(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    s = ts.strip()
    try:
        if s.endswith("Z"):
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _pick_latest_csv(godown_dir: Path) -> Path:
    if not godown_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"ANPR CSV folder not found for godown. Expected: {godown_dir}",
        )
    candidates = sorted(
        [p for p in godown_dir.glob("*.csv") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise HTTPException(status_code=404, detail="No ANPR CSV files found")
    return candidates[0]


def _read_events(csv_path: Path) -> list[_CsvEvent]:
    events: list[_CsvEvent] = []
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = _parse_ts(row.get("timestamp_utc") or "")
                if not ts:
                    continue
                camera_id = (row.get("camera_id") or "").strip()
                zone_id = (row.get("zone_id") or "").strip() or None
                plate_text = (row.get("plate_text") or "").strip()
                if not camera_id or not plate_text:
                    continue
                try:
                    det_conf = float(row.get("det_conf") or 0.0)
                    ocr_conf = float(row.get("ocr_conf") or 0.0)
                    combined_conf = float(row.get("combined_conf") or 0.0)
                except Exception:
                    det_conf, ocr_conf, combined_conf = 0.0, 0.0, 0.0
                match_status = (row.get("match_status") or "").strip() or "UNKNOWN"
                bbox = _parse_bbox(row.get("bbox"))

                events.append(
                    _CsvEvent(
                        timestamp_utc=ts,
                        camera_id=camera_id,
                        zone_id=zone_id,
                        plate_text=plate_text,
                        det_conf=det_conf,
                        ocr_conf=ocr_conf,
                        combined_conf=combined_conf,
                        match_status=match_status,
                        bbox=bbox,
                    )
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read CSV: {exc}")
    return events


def _to_local(ts_utc: datetime, tz_name: str) -> str:
    if ZoneInfo is None:
        return ts_utc.isoformat()
    try:
        tz = ZoneInfo(tz_name)
        return ts_utc.astimezone(tz).replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")
    except Exception:
        return ts_utc.isoformat()


def _event_type_from_status(status: str) -> str:
    s = (status or "").upper()
    if s == "VERIFIED":
        return "ANPR_PLATE_VERIFIED"
    if s in {"NOT_VERIFIED", "BLACKLIST"}:
        return "ANPR_PLATE_ALERT"
    if s == "TIME_VIOLATION":
        return "ANPR_TIME_VIOLATION"
    return "ANPR_PLATE_DETECTED"


@router.get("/csv-events")
def anpr_csv_events(
    godown_id: str = Query(..., description="Godown ID, e.g. GDN_SAMPLE"),
    timezone_name: str = Query("Asia/Kolkata", description="IANA timezone for local time rendering"),
    camera_id: Optional[str] = Query(None),
    plate_text: Optional[str] = Query(None),
    match_status: Optional[str] = Query(None, description="VERIFIED/NOT_VERIFIED/BLACKLIST/DEDUP..."),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
) -> dict[str, Any]:
    """Return ANPR events by reading the latest CSV for a godown.

    This is intentionally lightweight for the PoC: no DB writes.
    """

    base = _resolve_csv_dir()
    godown_dir = _safe_join(base, godown_id)
    try:
        csv_path = _pick_latest_csv(godown_dir)
    except HTTPException as exc:
        # Dynamic godowns may not have any CSVs yet; return an empty payload.
        if exc.status_code == 404:
            try:
                godown_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            return {
                "source": {"csv_path": "", "csv_mtime_utc": ""},
                "summary": {
                    "total": 0,
                    "verified": 0,
                    "not_verified": 0,
                    "blacklist": 0,
                    "dedup": 0,
                    "last_seen_local": None,
                },
                "events": [],
            }
        raise

    events = _read_events(csv_path)

    # Filters
    if camera_id:
        events = [e for e in events if e.camera_id == camera_id]
    if plate_text:
        events = [e for e in events if e.plate_text == plate_text]
    if match_status:
        ms = match_status.strip().upper()
        events = [e for e in events if (e.match_status or "").upper() == ms]

    if date_from or date_to:
        # compare using local date to match the dashboard expectation
        def _local_date(e: _CsvEvent) -> date:
            if ZoneInfo is None:
                return e.timestamp_utc.date()
            try:
                tz = ZoneInfo(timezone_name)
                return e.timestamp_utc.astimezone(tz).date()
            except Exception:
                return e.timestamp_utc.date()

        if date_from:
            events = [e for e in events if _local_date(e) >= date_from]
        if date_to:
            events = [e for e in events if _local_date(e) <= date_to]

    events.sort(key=lambda e: e.timestamp_utc, reverse=True)
    events = events[: int(limit)]

    # Summary (based on returned window)
    summary = {
        "total": len(events),
        "verified": sum(1 for e in events if (e.match_status or "").upper() == "VERIFIED"),
        "not_verified": sum(1 for e in events if (e.match_status or "").upper() == "NOT_VERIFIED"),
        "blacklist": sum(1 for e in events if (e.match_status or "").upper() == "BLACKLIST"),
        "dedup": sum(1 for e in events if (e.match_status or "").upper() == "DEDUP"),
    }
    last_seen_local = _to_local(events[0].timestamp_utc, timezone_name) if events else None

    return {
        "source": {
            "csv_path": str(csv_path),
            "csv_mtime_utc": datetime.fromtimestamp(csv_path.stat().st_mtime, tz=timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
        },
        "summary": {**summary, "last_seen_local": last_seen_local},
        "events": [
            {
                "timestamp_utc": e.timestamp_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "timestamp_local": _to_local(e.timestamp_utc, timezone_name),
                "camera_id": e.camera_id,
                "zone_id": e.zone_id,
                "plate_text": e.plate_text,
                "match_status": e.match_status,
                "event_type": _event_type_from_status(e.match_status),
                "det_conf": e.det_conf,
                "ocr_conf": e.ocr_conf,
                "combined_conf": e.combined_conf,
                "bbox": e.bbox,
            }
            for e in events
        ],
    }
