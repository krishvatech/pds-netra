from __future__ import annotations

import hmac
import time
import uuid
import uuid as uuidlib
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import ExpiredSignatureError, InvalidTokenError, decode_access_token
from app.models.camera import Camera
from app.models.edge_device import EdgeDevice
from app.schemas.camera import CameraOut
from app.services.live_frames import live_latest_path, live_latest_tmp_path

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


def _edge_auth(request: Request, db: Session) -> EdgeDevice | None:
    raw_key = request.headers.get("x-edge-key")
    if not raw_key:
        return None
    edge = db.execute(
        select(EdgeDevice).where(EdgeDevice.api_key == raw_key.strip(), EdgeDevice.is_active.is_(True))
    ).scalars().first()
    if not edge:
        raise HTTPException(status_code=401, detail="invalid_edge_key")
    return edge


def _get_camera_or_404(db: Session, camera_id: uuid.UUID, user_id: uuid.UUID | None, is_admin: bool) -> Camera:
    query = select(Camera).where(Camera.id == camera_id)
    if not is_admin and user_id is not None:
        query = query.where(Camera.user_id == user_id)
    camera = db.execute(query).scalars().first()
    if not camera:
        raise HTTPException(status_code=404, detail="camera_not_found")
    return camera


@router.get("", response_model=list[CameraOut])
def list_live_cameras(request: Request, db: Session = Depends(get_db)):
    edge = _edge_auth(request, db)
    if edge:
        query = select(Camera).where(
            Camera.is_active.is_(True),
            Camera.approval_status == "approved",
            Camera.edge_id == edge.id,
        )
        return db.execute(query.order_by(Camera.created_at.desc())).scalars().all()

    user_id, is_admin = _get_user_context(request)
    query = select(Camera).where(Camera.is_active.is_(True), Camera.approval_status == "approved")
    if not is_admin:
        query = query.where(Camera.user_id == user_id)
    return db.execute(query.order_by(Camera.created_at.desc())).scalars().all()


@router.post("/frame/{camera_id}", status_code=204)
def upload_live_frame(
    camera_id: uuid.UUID,
    request: Request,
    file: UploadFile,
    db: Session = Depends(get_db),
):
    edge = _edge_auth(request, db)
    if edge:
        camera = _get_camera_or_404(db, camera_id, None, True)
        if camera.approval_status != "approved":
            raise HTTPException(status_code=403, detail="camera_not_approved")
        if camera.edge_id != edge.id:
            raise HTTPException(status_code=403, detail="camera_not_allowed")
    else:
        user_id, is_admin = _get_user_context(request)
        camera = _get_camera_or_404(db, camera_id, user_id, is_admin)
        if camera.approval_status != "approved":
            raise HTTPException(status_code=403, detail="camera_not_approved")

    live_root = Path(settings.live_dir)
    live_root.mkdir(parents=True, exist_ok=True)

    tmp_path = live_latest_tmp_path(live_root, camera_id)
    if tmp_path.exists():
        try:
            tmp_path.unlink()
        except OSError:
            pass
    tmp_path = tmp_path.with_suffix(f".{uuidlib.uuid4().hex}.tmp")
    final_path = live_latest_path(live_root, camera_id)
    payload = file.file.read()
    tmp_path.write_bytes(payload)
    try:
        tmp_path.replace(final_path)
    except PermissionError:
        # Windows can lock the file if it is being read; fallback to direct write.
        final_path.write_bytes(payload)
        try:
            tmp_path.unlink()
        except OSError:
            pass
    return None


@router.get("/frame/{camera_id}")
def get_live_frame(camera_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    edge = _edge_auth(request, db)
    if edge:
        camera = _get_camera_or_404(db, camera_id, None, True)
        if camera.approval_status != "approved":
            raise HTTPException(status_code=403, detail="camera_not_approved")
        if camera.edge_id != edge.id:
            raise HTTPException(status_code=403, detail="camera_not_allowed")
    else:
        user_id, is_admin = _get_user_context(request)
        camera = _get_camera_or_404(db, camera_id, user_id, is_admin)
        if camera.approval_status != "approved":
            raise HTTPException(status_code=403, detail="camera_not_approved")

    live_root = Path(settings.live_dir)
    frame_path = live_latest_path(live_root, camera_id)
    if not frame_path.exists():
        raise HTTPException(status_code=404, detail="frame_not_found")

    try:
        data = frame_path.read_bytes()
    except PermissionError:
        raise HTTPException(status_code=503, detail="frame_busy")
    captured_at = frame_path.stat().st_mtime
    age_seconds = max(0.0, time.time() - captured_at)
    is_stale = age_seconds > settings.live_stale_threshold_sec

    headers = {
        "X-Frame-Captured-At": str(int(captured_at)),
        "X-Frame-Age-Seconds": f"{age_seconds:.2f}",
        "X-Frame-Stale": "true" if is_stale else "false",
        "X-Frame-Stale-Threshold-Seconds": str(settings.live_stale_threshold_sec),
    }
    return Response(content=data, media_type="image/jpeg", headers=headers)
