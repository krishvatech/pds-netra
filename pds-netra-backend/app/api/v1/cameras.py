"""
Camera configuration endpoints.
"""

from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.db import get_db
import os
from ...models.godown import Camera, Godown
from ...services.rule_seed import seed_rules_for_camera
from ...core.pagination import clamp_page_size, set_pagination_headers


router = APIRouter(prefix="/api/v1/cameras", tags=["cameras"])


class ZoneIn(BaseModel):
    id: str = Field(..., min_length=1)
    polygon: List[List[int]]


class ZoneUpdate(BaseModel):
    zones: List[ZoneIn]


class CameraModules(BaseModel):
    anpr_enabled: Optional[bool] = None
    gate_entry_exit_enabled: Optional[bool] = None
    person_after_hours_enabled: Optional[bool] = None
    animal_detection_enabled: Optional[bool] = None
    fire_detection_enabled: Optional[bool] = None
    health_monitoring_enabled: Optional[bool] = None


class CameraCreate(BaseModel):
    camera_id: str = Field(..., min_length=1)
    godown_id: str = Field(..., min_length=1)
    label: Optional[str] = None
    role: Optional[str] = None
    rtsp_url: str = Field(..., min_length=1)
    is_active: bool = True
    modules: Optional[CameraModules] = None


class CameraUpdate(BaseModel):
    label: Optional[str] = None
    role: Optional[str] = None
    rtsp_url: Optional[str] = None
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
        "is_active": camera.is_active,
        "zones_json": camera.zones_json,
        "modules": _parse_modules(camera.modules_json),
    }


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

def _get_camera(db: Session, camera_id: str, godown_id: Optional[str]) -> Camera:
    query = db.query(Camera).filter(Camera.id == camera_id)
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
) -> dict:
    camera = _get_camera(db, camera_id, godown_id)
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
) -> dict:
    camera = _get_camera(db, camera_id, godown_id)
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
    godown_id: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
    response: Response,
) -> list[dict]:
    page_size = clamp_page_size(page_size)
    query = db.query(Camera)
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
def create_camera(payload: CameraCreate, db: Session = Depends(get_db)) -> dict:
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
) -> dict:
    camera = _get_camera(db, camera_id, godown_id)
    if payload.label is not None:
        camera.label = payload.label
    if payload.role is not None:
        camera.role = payload.role
    if payload.rtsp_url is not None:
        camera.rtsp_url = payload.rtsp_url
    if payload.is_active is not None:
        camera.is_active = payload.is_active
    if payload.modules is not None:
        modules_data = payload.modules.model_dump(exclude_none=True)
        camera.modules_json = json.dumps(modules_data) if modules_data else None
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return _camera_payload(camera)


@router.delete("/{camera_id}")
def delete_camera(
    camera_id: str,
    godown_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    camera = _get_camera(db, camera_id, godown_id)
    db.delete(camera)
    db.commit()
    return {"status": "deleted", "camera_id": camera_id}
