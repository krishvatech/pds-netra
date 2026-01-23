"""
Camera configuration endpoints.
"""

from __future__ import annotations

import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.godown import Camera


router = APIRouter(prefix="/api/v1/cameras", tags=["cameras"])


class ZoneIn(BaseModel):
    id: str = Field(..., min_length=1)
    polygon: List[List[int]]


class ZoneUpdate(BaseModel):
    zones: List[ZoneIn]


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
