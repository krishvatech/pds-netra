"""
Godown endpoints for PDS Netra backend.

Provides list and detail views used by the dashboard.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional
from pathlib import Path
import json

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
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

def _parse_modules(modules_json: str | None) -> Optional[dict]:
    if not modules_json:
        return None
    try:
        data = json.loads(modules_json)
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None

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
            {
                "camera_id": c.id,
                "label": c.label,
                "role": c.role,
                "rtsp_url": c.rtsp_url,
                "is_active": c.is_active,
                "zones_json": c.zones_json,
                "modules": _parse_modules(c.modules_json),
            }
            for c in cameras
        ],
        "summary": {
            "alerts_last_24h": alerts_last_24h,
            "critical_alerts_last_24h": critical_last_24h,
            "last_event_time_utc": last_event[0] if last_event else None,
        },
    }


class CreateGodownRequest(BaseModel):
    godown_id: str = Field(..., max_length=64)
    name: Optional[str] = None
    district: Optional[str] = None
    code: Optional[str] = None


@router.post("", status_code=201)
def create_godown(req: CreateGodownRequest, db: Session = Depends(get_db)) -> dict:
    godown_id = req.godown_id.strip()
    if not godown_id:
        raise HTTPException(status_code=400, detail="godown_id cannot be empty")

    # Check if exists
    existing = db.get(Godown, godown_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Godown {godown_id} already exists")

    # Create record
    new_g = Godown(
        id=godown_id,
        name=req.name,
        district=req.district,
        code=req.code,
    )
    db.add(new_g)
    db.commit()
    db.refresh(new_g)

    # Create directories
    # Root: pds-netra-backend/app/api/v1/godowns.py (this file)
    # parents[3] => pds-netra-backend/
    data_root = Path(__file__).resolve().parents[3] / "data"
    dirs = ["live", "annotated", "snapshots", "uploads"]
    for d in dirs:
        (data_root / d / godown_id).mkdir(parents=True, exist_ok=True)

    # Return GodownDetail-like object
    return {
        "godown_id": new_g.id,
        "name": new_g.name,
        "district": new_g.district,
        "capacity": None,
        "cameras": [],
        "summary": {
            "alerts_last_24h": 0,
            "critical_alerts_last_24h": 0,
            "last_event_time_utc": None,
        },
    }


class UpdateGodownRequest(BaseModel):
    name: Optional[str] = None
    district: Optional[str] = None
    code: Optional[str] = None


@router.put("/{godown_id}")
def update_godown(godown_id: str, req: UpdateGodownRequest, db: Session = Depends(get_db)) -> dict:
    godown = db.get(Godown, godown_id)
    if not godown:
        raise HTTPException(status_code=404, detail="Godown not found")

    if req.name is not None:
        godown.name = req.name
    if req.district is not None:
        godown.district = req.district
    if req.code is not None:
        godown.code = req.code

    db.commit()
    db.refresh(godown)

    return get_godown_detail(godown_id, db)


@router.delete("/{godown_id}")
def delete_godown(godown_id: str, db: Session = Depends(get_db)) -> dict:
    """
    Delete a godown and all related data.
    
    This will remove:
    - The godown record
    - All cameras (via cascade)
    - All events with this godown_id
    - All alerts with this godown_id
    - All rules with this godown_id
    - All test runs with this godown_id
    - All media directories (live, annotated, snapshots, uploads)
    """
    from ...models.event import Event, Alert
    from ...models.rule import Rule
    from ...services.test_runs import delete_test_run, list_test_runs
    import shutil
    
    godown = db.get(Godown, godown_id)
    if not godown:
        raise HTTPException(status_code=404, detail="Godown not found")

    # Count what will be deleted for logging
    events_count = db.query(func.count(Event.id)).filter(Event.godown_id == godown_id).scalar() or 0
    alerts_count = db.query(func.count(Alert.id)).filter(Alert.godown_id == godown_id).scalar() or 0
    
    # Delete all test runs for this godown
    test_runs = list_test_runs()
    deleted_runs = 0
    for run in test_runs:
        if run.get("godown_id") == godown_id:
            try:
                delete_test_run(run["run_id"])
                deleted_runs += 1
            except Exception:
                pass  # Continue even if individual test run deletion fails

    # Delete all events
    db.query(Event).filter(Event.godown_id == godown_id).delete(synchronize_session=False)
    
    # Delete all alerts
    db.query(Alert).filter(Alert.godown_id == godown_id).delete(synchronize_session=False)
    
    # Delete all rules
    from ...models.rule import Rule
    db.query(Rule).filter(Rule.godown_id == godown_id).delete(synchronize_session=False)
    
    # Delete the godown (cameras will be cascade deleted)
    db.delete(godown)
    db.commit()

    # Delete media directories
    data_root = Path(__file__).resolve().parents[3] / "data"
    dirs_to_remove = ["live", "annotated", "snapshots", "uploads"]
    removed_dirs = []
    
    for dir_name in dirs_to_remove:
        dir_path = data_root / dir_name / godown_id
        if dir_path.exists():
            try:
                shutil.rmtree(dir_path)
                removed_dirs.append(dir_name)
            except Exception:
                pass  # Continue even if directory deletion fails

    return {
        "status": "success",
        "message": f"Godown {godown_id} and all related data deleted",
        "deleted": {
            "events": events_count,
            "alerts": alerts_count,
            "test_runs": deleted_runs,
            "media_directories": removed_dirs
        }
    }