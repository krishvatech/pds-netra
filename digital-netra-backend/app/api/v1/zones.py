from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import ExpiredSignatureError, InvalidTokenError, decode_access_token
from app.models.camera import Camera
from app.models.zone import Zone
from app.schemas.zone import ZoneCreate, ZoneOut, ZoneUpdate

router = APIRouter(redirect_slashes=False)
SESSION_COOKIE = "dn_session"


def _get_user_context(request: Request) -> tuple[uuid.UUID, bool]:
    token = None
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
    if not token:
        token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="missing_token")

    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token_expired")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid_token")

    raw_user_id = payload.get("user_id")
    if not raw_user_id:
        raise HTTPException(status_code=401, detail="invalid_token")

    try:
        user_id = uuid.UUID(str(raw_user_id))
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid_token")
    is_admin = bool(payload.get("is_admin", False))
    return user_id, is_admin


def _get_camera_or_404(db: Session, camera_id: uuid.UUID, user_id: uuid.UUID, is_admin: bool) -> Camera:
    query = select(Camera).where(Camera.id == camera_id)
    if not is_admin:
        query = query.where(Camera.user_id == user_id)
    camera = db.execute(query).scalars().first()
    if not camera:
        raise HTTPException(status_code=404, detail="camera_not_found")
    return camera


def _get_zone_or_404(db: Session, zone_id: uuid.UUID, camera_id: uuid.UUID) -> Zone:
    zone = db.execute(
        select(Zone).where(Zone.id == zone_id, Zone.camera_id == camera_id)
    ).scalars().first()
    if not zone:
        raise HTTPException(status_code=404, detail="zone_not_found")
    return zone


@router.get("/cameras/{camera_id}/zones", response_model=list[ZoneOut])
def list_zones(camera_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    user_id, is_admin = _get_user_context(request)
    _get_camera_or_404(db, camera_id, user_id, is_admin)
    return db.execute(select(Zone).where(Zone.camera_id == camera_id).order_by(Zone.created_at.desc())).scalars().all()


@router.post("/cameras/{camera_id}/zones", response_model=ZoneOut, status_code=201)
def create_zone(camera_id: uuid.UUID, payload: ZoneCreate, request: Request, db: Session = Depends(get_db)):
    user_id, is_admin = _get_user_context(request)
    _get_camera_or_404(db, camera_id, user_id, is_admin)
    zone = Zone(
        camera_id=camera_id,
        zone_name=payload.zone_name.strip(),
        polygon=payload.polygon,
        is_active=payload.is_active,
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


@router.get("/cameras/{camera_id}/zones/{zone_id}", response_model=ZoneOut)
def get_zone(camera_id: uuid.UUID, zone_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    user_id, is_admin = _get_user_context(request)
    _get_camera_or_404(db, camera_id, user_id, is_admin)
    return _get_zone_or_404(db, zone_id, camera_id)


@router.put("/cameras/{camera_id}/zones/{zone_id}", response_model=ZoneOut)
def update_zone(
    camera_id: uuid.UUID,
    zone_id: uuid.UUID,
    payload: ZoneUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, is_admin = _get_user_context(request)
    _get_camera_or_404(db, camera_id, user_id, is_admin)
    zone = _get_zone_or_404(db, zone_id, camera_id)

    if payload.zone_name is not None:
        zone.zone_name = payload.zone_name.strip()
    if payload.polygon is not None:
        zone.polygon = payload.polygon
    if payload.is_active is not None:
        zone.is_active = payload.is_active

    db.commit()
    db.refresh(zone)
    return zone


@router.delete("/cameras/{camera_id}/zones/{zone_id}", status_code=204)
def delete_zone(camera_id: uuid.UUID, zone_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    user_id, is_admin = _get_user_context(request)
    _get_camera_or_404(db, camera_id, user_id, is_admin)
    zone = _get_zone_or_404(db, zone_id, camera_id)
    db.delete(zone)
    db.commit()
    return None
