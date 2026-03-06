"""File-backed workstation configuration for station monitoring."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from ..core.errors import safe_json_dump_atomic, safe_json_load
from ..models.godown import Camera
from ..models.rule import Rule
from .test_runs import data_dir

logger = logging.getLogger("station_workstations")

STATUSES = {"ACTIVE", "ON_LEAVE", "DISABLED"}
WORKSTATION_RULE_TYPE = "WORKSTATION_ABSENCE"


@dataclass
class WorkstationConfig:
    godown_id: str
    camera_id: str
    zone_id: str
    seat_label: Optional[str] = None
    employee_name: Optional[str] = None
    status: str = "ACTIVE"
    shift_start: Optional[str] = None
    shift_end: Optional[str] = None
    break_start: Optional[str] = None
    break_end: Optional[str] = None
    leave_from: Optional[str] = None
    leave_to: Optional[str] = None
    updated_at: Optional[str] = None


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _store_path() -> Path:
    return data_dir() / "station_monitoring" / "workstations.json"


def _load_rows() -> List[Dict[str, Any]]:
    loaded = safe_json_load(_store_path(), [], logger=logger)
    if isinstance(loaded, list):
        return [row for row in loaded if isinstance(row, dict)]
    return []


def _save_rows(rows: List[Dict[str, Any]]) -> bool:
    return safe_json_dump_atomic(_store_path(), rows, logger=logger)


def _normalize_status(raw: Optional[str]) -> str:
    value = (raw or "ACTIVE").strip().upper()
    return value if value in STATUSES else "ACTIVE"


def _row_key(godown_id: str, camera_id: str, zone_id: str) -> str:
    return f"{godown_id}::{camera_id}::{zone_id}"


def _normalize_zone_ids(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        items = [str(part).strip() for part in value]
    else:
        return []
    normalized: List[str] = []
    seen: Set[str] = set()
    for item in items:
        if not item or item.lower() in {"all", "*", "__global__", "global"}:
            continue
        if item not in seen:
            normalized.append(item)
            seen.add(item)
    return normalized


def _parse_camera_zone_ids(camera: Camera) -> List[str]:
    raw = camera.zones_json
    if not raw:
        return []
    try:
        payload = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    zones: List[str] = []
    seen: Set[str] = set()
    for zone in payload:
        if not isinstance(zone, dict):
            continue
        zone_id = str(zone.get("id") or "").strip()
        if not zone_id or zone_id in seen:
            continue
        zones.append(zone_id)
        seen.add(zone_id)
    return zones


def _camera_rule_zone_map(db: Session, *, godown_id: Optional[str] = None, camera_id: Optional[str] = None) -> Dict[tuple[str, str], Set[str]]:
    query = db.query(Rule).filter(
        Rule.enabled == True,  # noqa: E712
        Rule.type == WORKSTATION_RULE_TYPE,
    )
    if godown_id:
        query = query.filter(Rule.godown_id == godown_id)
    if camera_id:
        query = query.filter(Rule.camera_id == camera_id)

    camera_query = db.query(Camera)
    if godown_id:
        camera_query = camera_query.filter(Camera.godown_id == godown_id)
    if camera_id:
        camera_query = camera_query.filter(Camera.id == camera_id)
    cameras = camera_query.all()
    camera_zone_lookup = {
        (str(cam.godown_id), str(cam.id)): set(_parse_camera_zone_ids(cam))
        for cam in cameras
    }

    mapping: Dict[tuple[str, str], Set[str]] = {}
    for rule in query.all():
        key = (str(rule.godown_id), str(rule.camera_id))
        selected = set(_normalize_zone_ids((rule.params or {}).get("zone_ids")))
        zone_id = str(rule.zone_id or "").strip()
        if not selected and zone_id and zone_id.lower() not in {"all", "*", "__global__", "global"}:
            selected.add(zone_id)
        if zone_id.lower() in {"all", "*", "__global__", "global"}:
            selected |= camera_zone_lookup.get(key, set())
        if not selected:
            continue
        mapping.setdefault(key, set()).update(selected)
    return mapping


def list_workstations(
    db: Session,
    *,
    godown_id: Optional[str] = None,
    camera_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    rows = _load_rows()
    indexed = {
        _row_key(str(row.get("godown_id") or ""), str(row.get("camera_id") or ""), str(row.get("zone_id") or "")): row
        for row in rows
    }

    query = db.query(Camera)
    if godown_id:
        query = query.filter(Camera.godown_id == godown_id)
    if camera_id:
        query = query.filter(Camera.id == camera_id)
    rule_zone_map = _camera_rule_zone_map(db, godown_id=godown_id, camera_id=camera_id)

    items: List[Dict[str, Any]] = []
    for camera in query.all():
        zone_ids = sorted(rule_zone_map.get((str(camera.godown_id), str(camera.id)), set()))
        for zone_id in zone_ids:
            key = _row_key(str(camera.godown_id), str(camera.id), zone_id)
            saved = indexed.get(key, {})
            item = WorkstationConfig(
                godown_id=str(camera.godown_id),
                camera_id=str(camera.id),
                zone_id=zone_id,
                seat_label=saved.get("seat_label"),
                employee_name=saved.get("employee_name"),
                status=_normalize_status(saved.get("status")),
                shift_start=saved.get("shift_start"),
                shift_end=saved.get("shift_end"),
                break_start=saved.get("break_start"),
                break_end=saved.get("break_end"),
                leave_from=saved.get("leave_from"),
                leave_to=saved.get("leave_to"),
                updated_at=saved.get("updated_at"),
            )
            items.append(asdict(item))
    items.sort(key=lambda row: (row["camera_id"], row["zone_id"]))
    return items


def is_monitored_workstation_zone(
    db: Session,
    *,
    godown_id: str,
    camera_id: str,
    zone_id: str,
) -> bool:
    mapping = _camera_rule_zone_map(db, godown_id=godown_id, camera_id=camera_id)
    return zone_id in mapping.get((godown_id, camera_id), set())


def upsert_workstation(
    *,
    godown_id: str,
    camera_id: str,
    zone_id: str,
    seat_label: Optional[str] = None,
    employee_name: Optional[str] = None,
    status: Optional[str] = None,
    shift_start: Optional[str] = None,
    shift_end: Optional[str] = None,
    break_start: Optional[str] = None,
    break_end: Optional[str] = None,
    leave_from: Optional[str] = None,
    leave_to: Optional[str] = None,
) -> Dict[str, Any]:
    rows = _load_rows()
    key = _row_key(godown_id, camera_id, zone_id)
    next_row: Dict[str, Any] = {
        "godown_id": godown_id,
        "camera_id": camera_id,
        "zone_id": zone_id,
        "seat_label": seat_label or None,
        "employee_name": employee_name or None,
        "status": _normalize_status(status),
        "shift_start": shift_start or None,
        "shift_end": shift_end or None,
        "break_start": break_start or None,
        "break_end": break_end or None,
        "leave_from": leave_from or None,
        "leave_to": leave_to or None,
        "updated_at": _utc_now(),
    }

    replaced = False
    for idx, row in enumerate(rows):
        row_key = _row_key(str(row.get("godown_id") or ""), str(row.get("camera_id") or ""), str(row.get("zone_id") or ""))
        if row_key == key:
            rows[idx] = next_row
            replaced = True
            break
    if not replaced:
        rows.append(next_row)

    _save_rows(rows)
    return next_row
