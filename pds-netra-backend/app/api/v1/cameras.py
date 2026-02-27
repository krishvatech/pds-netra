"""
Camera configuration endpoints.
"""

from __future__ import annotations

import json
from typing import List, Optional, Tuple
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.db import get_db
import os
from ...models.godown import Camera, Godown
from ...core.auth import UserContext, get_current_user
from ...services.rule_seed import seed_rules_for_camera
from ...services.live_frames import remove_live_frame_artifacts
from ...core.pagination import clamp_page_size, set_pagination_headers


router = APIRouter(prefix="/api/v1/cameras", tags=["cameras"])


ADMIN_ROLES = {"STATE_ADMIN", "HQ_ADMIN"}


def _is_admin(user: UserContext) -> bool:
    return (user.role or "").upper() in ADMIN_ROLES


def _camera_query_for_user(db: Session, user: UserContext):
    query = db.query(Camera)
    if _is_admin(user):
        return query
    if not user.user_id:
        return query.filter(Camera.godown_id == "__forbidden__")
    return query.join(Godown, Godown.id == Camera.godown_id).filter(Godown.created_by_user_id == user.user_id)


class ZoneIn(BaseModel):
    id: str = Field(..., min_length=1)
    # Accept both normalized points (0..1 floats) and absolute pixel points.
    # Tuple enforces exactly 2 coordinates per point.
    polygon: List[Tuple[float, float]]


class ZoneUpdate(BaseModel):
    zones: List[ZoneIn]


class CameraModules(BaseModel):
    anpr_enabled: Optional[bool] = None
    gate_entry_exit_enabled: Optional[bool] = None
    person_after_hours_enabled: Optional[bool] = None
    animal_detection_enabled: Optional[bool] = None
    fire_detection_enabled: Optional[bool] = None
    phone_usage_enabled: Optional[bool] = None
    health_monitoring_enabled: Optional[bool] = None


class CameraCreate(BaseModel):
    camera_id: str = Field(..., min_length=1)
    godown_id: str = Field(..., min_length=1)
    label: Optional[str] = None
    role: Optional[str] = None
    rtsp_url: str = Field(..., min_length=1)
    source_type: Optional[str] = Field(default=None, pattern="^(live|test)$")
    source_path: Optional[str] = None
    source_run_id: Optional[str] = None
    is_active: bool = True
    modules: Optional[CameraModules] = None


class CameraUpdate(BaseModel):
    label: Optional[str] = None
    role: Optional[str] = None
    rtsp_url: Optional[str] = None
    source_type: Optional[str] = Field(default=None, pattern="^(live|test)$")
    source_path: Optional[str] = None
    source_run_id: Optional[str] = None
    is_active: Optional[bool] = None
    modules: Optional[CameraModules] = None


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


def _camera_payload(camera: Camera) -> dict:
    return {
        "camera_id": camera.id,
        "godown_id": camera.godown_id,
        "label": camera.label,
        "role": camera.role,
        "rtsp_url": camera.rtsp_url,
        "source_type": camera.source_type or "live",
        "source_path": camera.source_path,
        "source_run_id": camera.source_run_id,
        "is_active": camera.is_active,
        "zones_json": camera.zones_json,
        "modules": _parse_modules(camera.modules_json),
    }


def _live_root() -> Path:
    return Path(
        os.getenv("PDS_LIVE_DIR", str(Path(__file__).resolve().parents[3] / "data" / "live"))
    ).expanduser()


def _remove_live_latest_frame(godown_id: str, camera_id: str) -> None:
    try:
        remove_live_frame_artifacts(
            _live_root(),
            godown_id,
            camera_id,
            include_latest=True,
            include_subdirs=True,
        )
    except Exception:
        # Best effort cleanup; camera CRUD should not fail if file delete fails.
        pass


def _parse_zones(zones_json: str | None) -> List[dict]:
    if not zones_json:
        return []
    try:
        data = json.loads(zones_json)
        if isinstance(data, list):
            return data
    except Exception:
        return []
    return []

def _get_camera(db: Session, camera_id: str, godown_id: Optional[str], user: UserContext) -> Camera:
    query = _camera_query_for_user(db, user).filter(Camera.id == camera_id)
    if godown_id:
        camera = query.filter(Camera.godown_id == godown_id).first()
        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")
        return camera
    cameras = query.all()
    if not cameras:
        raise HTTPException(status_code=404, detail="Camera not found")
    if len(cameras) > 1:
        raise HTTPException(status_code=409, detail="Multiple cameras share this id; specify godown_id")
    return cameras[0]


@router.get("/{camera_id}/zones")
def get_camera_zones(
    camera_id: str,
    godown_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    camera = _get_camera(db, camera_id, godown_id, user)
    return {
        "camera_id": camera.id,
        "godown_id": camera.godown_id,
        "zones": _parse_zones(camera.zones_json),
    }


@router.put("/{camera_id}/zones")
def update_camera_zones(
    camera_id: str,
    payload: ZoneUpdate,
    godown_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    camera = _get_camera(db, camera_id, godown_id, user)
    zones = [z.model_dump() for z in payload.zones]
    camera.zones_json = json.dumps(zones)
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return {
        "camera_id": camera.id,
        "godown_id": camera.godown_id,
        "zones": zones,
    }


@router.get("")
def list_cameras(
    response: Response,
    godown_id: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> list[dict]:
    page_size = clamp_page_size(page_size)
    query = _camera_query_for_user(db, user)
    if godown_id:
        query = query.filter(Camera.godown_id == godown_id)
    if role:
        query = query.filter(Camera.role == role)
    if is_active is not None:
        query = query.filter(Camera.is_active == is_active)
    total = query.count()
    cameras = (
        query.order_by(Camera.godown_id.asc(), Camera.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    set_pagination_headers(response, total=total, page=page, page_size=page_size)
    return [_camera_payload(camera) for camera in cameras]


@router.post("")
def create_camera(
    payload: CameraCreate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    existing = (
        db.query(Camera)
        .filter(Camera.id == payload.camera_id, Camera.godown_id == payload.godown_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Camera already exists")
    godown = db.get(Godown, payload.godown_id)
    if not godown:
        raise HTTPException(status_code=404, detail="Godown not found")
    if not _is_admin(user) and (not user.user_id or godown.created_by_user_id != user.user_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    modules_json = None
    if payload.modules is not None:
        modules_data = payload.modules.model_dump(exclude_none=True)
        modules_json = json.dumps(modules_data) if modules_data else None
    camera = Camera(
        id=payload.camera_id,
        godown_id=payload.godown_id,
        label=payload.label,
        role=payload.role,
        rtsp_url=payload.rtsp_url,
        source_type=payload.source_type or "live",
        source_path=payload.source_path if (payload.source_type or "live") == "test" else None,
        source_run_id=payload.source_run_id if (payload.source_type or "live") == "test" else None,
        is_active=payload.is_active,
        modules_json=modules_json,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    if os.getenv("AUTO_SEED_RULES", "true").lower() in {"1", "true", "yes"}:
        seed_rules_for_camera(db, camera)
    return _camera_payload(camera)


@router.put("/{camera_id}")
def update_camera(
    camera_id: str,
    payload: CameraUpdate,
    godown_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    camera = _get_camera(db, camera_id, godown_id, user)
    prev_is_active = camera.is_active
    if payload.label is not None:
        camera.label = payload.label
    if payload.role is not None:
        camera.role = payload.role
    if payload.rtsp_url is not None:
        camera.rtsp_url = payload.rtsp_url
    if payload.source_type is not None:
        camera.source_type = payload.source_type
        if payload.source_type == "live":
            camera.source_path = None
            camera.source_run_id = None
    if payload.source_path is not None:
        camera.source_path = payload.source_path
    if payload.source_run_id is not None:
        camera.source_run_id = payload.source_run_id
    if payload.is_active is not None:
        camera.is_active = payload.is_active
    if payload.modules is not None:
        modules_data = payload.modules.model_dump(exclude_none=True)
        camera.modules_json = json.dumps(modules_data) if modules_data else None
    db.add(camera)
    db.commit()
    db.refresh(camera)
    if prev_is_active and camera.is_active is False:
        _remove_live_latest_frame(camera.godown_id, camera.id)
    return _camera_payload(camera)


@router.delete("/{camera_id}")
def delete_camera(
    camera_id: str,
    godown_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    camera = _get_camera(db, camera_id, godown_id, user)
    camera_key = camera.id
    godown_key = camera.godown_id
    db.delete(camera)
    db.commit()
    _remove_live_latest_frame(godown_key, camera_key)
    return {"status": "deleted", "camera_id": camera_id}
