"""
Camera configuration endpoints.
"""

from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.db import get_db
import os
from ...models.godown import Camera, Godown
from ...services.rule_seed import seed_rules_for_camera


router = APIRouter(prefix="/api/v1/cameras", tags=["cameras"])


class ZoneIn(BaseModel):
    id: str = Field(..., min_length=1)
    polygon: List[List[int]]


class ZoneUpdate(BaseModel):
    zones: List[ZoneIn]

class CameraCreate(BaseModel):
    camera_id: str = Field(..., min_length=1)
    godown_id: str = Field(..., min_length=1)
    label: Optional[str] = None
    role: Optional[str] = None
    rtsp_url: str = Field(..., min_length=1)
    is_active: bool = True


class CameraUpdate(BaseModel):
    label: Optional[str] = None
    role: Optional[str] = None
    rtsp_url: Optional[str] = None
    is_active: Optional[bool] = None


def _camera_payload(camera: Camera) -> dict:
    return {
        "camera_id": camera.id,
        "godown_id": camera.godown_id,
        "label": camera.label,
        "role": camera.role,
        "rtsp_url": camera.rtsp_url,
        "is_active": camera.is_active,
        "zones_json": camera.zones_json,
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


@router.get("/{camera_id}/zones")
def get_camera_zones(camera_id: str, db: Session = Depends(get_db)) -> dict:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return {
        "camera_id": camera.id,
        "godown_id": camera.godown_id,
        "zones": _parse_zones(camera.zones_json),
    }


@router.put("/{camera_id}/zones")
def update_camera_zones(camera_id: str, payload: ZoneUpdate, db: Session = Depends(get_db)) -> dict:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
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


@router.post("")
def create_camera(payload: CameraCreate, db: Session = Depends(get_db)) -> dict:
    existing = db.get(Camera, payload.camera_id)
    if existing:
        raise HTTPException(status_code=409, detail="Camera already exists")
    godown = db.get(Godown, payload.godown_id)
    if not godown:
        raise HTTPException(status_code=404, detail="Godown not found")
    camera = Camera(
        id=payload.camera_id,
        godown_id=payload.godown_id,
        label=payload.label,
        role=payload.role,
        rtsp_url=payload.rtsp_url,
        is_active=payload.is_active,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    if os.getenv("AUTO_SEED_RULES", "true").lower() in {"1", "true", "yes"}:
        seed_rules_for_camera(db, camera)
    return _camera_payload(camera)


@router.put("/{camera_id}")
def update_camera(camera_id: str, payload: CameraUpdate, db: Session = Depends(get_db)) -> dict:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    if payload.label is not None:
        camera.label = payload.label
    if payload.role is not None:
        camera.role = payload.role
    if payload.rtsp_url is not None:
        camera.rtsp_url = payload.rtsp_url
    if payload.is_active is not None:
        camera.is_active = payload.is_active
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return _camera_payload(camera)


@router.delete("/{camera_id}")
def delete_camera(camera_id: str, db: Session = Depends(get_db)) -> dict:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    db.delete(camera)
    db.commit()
    return {"status": "deleted", "camera_id": camera_id}