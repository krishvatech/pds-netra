from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import ExpiredSignatureError, InvalidTokenError, decode_access_token
from app.models.camera import Camera
from app.schemas.camera import CameraCreate, CameraOut, CameraUpdate

router = APIRouter(redirect_slashes=False)
SESSION_COOKIE = "dn_session"


def _get_user_id(request: Request) -> uuid.UUID:
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
        return uuid.UUID(str(raw_user_id))
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid_token")


def _get_camera_or_404(db: Session, camera_id: uuid.UUID, user_id: uuid.UUID) -> Camera:
    camera = db.execute(
        select(Camera).where(Camera.id == camera_id, Camera.user_id == user_id)
    ).scalars().first()
    if not camera:
        raise HTTPException(status_code=404, detail="camera_not_found")
    return camera


@router.get("", response_model=list[CameraOut])
def list_cameras(request: Request, db: Session = Depends(get_db)):
    user_id = _get_user_id(request)
    return db.execute(select(Camera).where(Camera.user_id == user_id).order_by(Camera.created_at.desc())).scalars().all()


@router.post("", response_model=CameraOut, status_code=201)
def create_camera(payload: CameraCreate, request: Request, db: Session = Depends(get_db)):
    user_id = _get_user_id(request)
    camera = Camera(
        camera_name=payload.camera_name.strip(),
        role=payload.role.strip(),
        rtsp_url=payload.rtsp_url.strip(),
        is_active=payload.is_active,
        user_id=user_id,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    user_id = _get_user_id(request)
    return _get_camera_or_404(db, camera_id, user_id)


@router.put("/{camera_id}", response_model=CameraOut)
def update_camera(camera_id: uuid.UUID, payload: CameraUpdate, request: Request, db: Session = Depends(get_db)):
    user_id = _get_user_id(request)
    camera = _get_camera_or_404(db, camera_id, user_id)

    if payload.camera_name is not None:
        camera.camera_name = payload.camera_name.strip()
    if payload.role is not None:
        camera.role = payload.role.strip()
    if payload.rtsp_url is not None:
        camera.rtsp_url = payload.rtsp_url.strip()
    if payload.is_active is not None:
        camera.is_active = payload.is_active

    db.commit()
    db.refresh(camera)
    return camera


@router.delete("/{camera_id}", status_code=204)
def delete_camera(camera_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    user_id = _get_user_id(request)
    camera = _get_camera_or_404(db, camera_id, user_id)
    db.delete(camera)
    db.commit()
    return None
