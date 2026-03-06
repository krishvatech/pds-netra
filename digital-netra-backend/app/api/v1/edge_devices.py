from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import ExpiredSignatureError, InvalidTokenError, decode_access_token
from app.models.app_user import AppUser
from app.models.edge_device import EdgeDevice
from app.schemas.edge_device import EdgeDeviceCreate, EdgeDeviceOut, EdgeDeviceUpdate

router = APIRouter(redirect_slashes=False)
SESSION_COOKIE = "dn_session"


def _get_auth_context(request: Request) -> tuple[uuid.UUID, bool]:
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

    is_admin = bool(payload.get("is_admin"))
    return user_id, is_admin


def _ensure_user_exists(db: Session, user_id: uuid.UUID) -> None:
    exists = db.execute(select(AppUser.id).where(AppUser.id == user_id)).scalars().first()
    if not exists:
        raise HTTPException(status_code=404, detail="user_not_found")


@router.get("", response_model=list[EdgeDeviceOut])
def list_edge_devices(
    request: Request,
    user_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    auth_user_id, is_admin = _get_auth_context(request)

    query = select(EdgeDevice).order_by(EdgeDevice.created_at.desc())
    if is_admin:
        if user_id:
            query = query.where(EdgeDevice.user_id == user_id)
    else:
        query = query.where(EdgeDevice.user_id == auth_user_id)
    return db.execute(query).scalars().all()


@router.post("", response_model=EdgeDeviceOut, status_code=201)
def create_edge_device(payload: EdgeDeviceCreate, request: Request, db: Session = Depends(get_db)):
    _, is_admin = _get_auth_context(request)
    if not is_admin:
        raise HTTPException(status_code=403, detail="admin_only")

    _ensure_user_exists(db, payload.user_id)

    edge = EdgeDevice(
        name=payload.name.strip(),
        api_key=payload.api_key.strip(),
        is_active=payload.is_active,
        location=payload.location.strip(),
        ip=payload.ip.strip(),
        password=payload.password.strip(),
        user_id=payload.user_id,
    )
    db.add(edge)
    db.commit()
    db.refresh(edge)
    return edge


@router.put("/{edge_id}", response_model=EdgeDeviceOut)
def update_edge_device(edge_id: uuid.UUID, payload: EdgeDeviceUpdate, request: Request, db: Session = Depends(get_db)):
    _, is_admin = _get_auth_context(request)
    if not is_admin:
        raise HTTPException(status_code=403, detail="admin_only")

    edge = db.get(EdgeDevice, edge_id)
    if not edge:
        raise HTTPException(status_code=404, detail="edge_not_found")

    if payload.user_id is not None:
        _ensure_user_exists(db, payload.user_id)
        edge.user_id = payload.user_id
    if payload.name is not None:
        edge.name = payload.name.strip()
    if payload.api_key is not None:
        edge.api_key = payload.api_key.strip()
    if payload.is_active is not None:
        edge.is_active = payload.is_active
    if payload.location is not None:
        edge.location = payload.location.strip()
    if payload.ip is not None:
        edge.ip = payload.ip.strip()
    if payload.password is not None:
        edge.password = payload.password.strip()

    db.commit()
    db.refresh(edge)
    return edge


@router.delete("/{edge_id}", status_code=204)
def delete_edge_device(edge_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    _, is_admin = _get_auth_context(request)
    if not is_admin:
        raise HTTPException(status_code=403, detail="admin_only")

    edge = db.get(EdgeDevice, edge_id)
    if not edge:
        raise HTTPException(status_code=404, detail="edge_not_found")
    db.delete(edge)
    db.commit()
    return None
