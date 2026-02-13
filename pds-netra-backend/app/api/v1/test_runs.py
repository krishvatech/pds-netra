"""
Test run upload and activation endpoints.
"""

from __future__ import annotations

import shutil
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Query, Depends
from fastapi.responses import StreamingResponse
from pathlib import Path
import time

from ...core.auth import UserContext, get_current_user
from ...services.test_runs import (
    create_test_run,
    delete_test_run,
    get_test_run,
    list_test_runs,
    update_test_run,
    write_edge_override,
)
from ...core.db import SessionLocal
from ...models.godown import Camera, Godown
from ...models.event import Alert
from ...core.pagination import clamp_page_size
from ...core.request_limits import enforce_upload_limit, copy_upload_file


router = APIRouter(prefix="/api/v1/test-runs", tags=["test-runs"])
ADMIN_ROLES = {"STATE_ADMIN", "HQ_ADMIN"}


def _is_admin(user: UserContext) -> bool:
    return (user.role or "").upper() in ADMIN_ROLES


def _can_access_godown(user: UserContext, godown_id: str) -> bool:
    if _is_admin(user):
        return True
    if not user.user_id:
        return False
    with SessionLocal() as db:
        godown = db.get(Godown, godown_id)
        if not godown:
            return False
        return godown.created_by_user_id == user.user_id


def _assert_run_access(user: UserContext, run: dict) -> None:
    godown_id = str(run.get("godown_id") or "")
    if not godown_id:
        raise HTTPException(status_code=404, detail="Test run not found")
    if not _can_access_godown(user, godown_id):
        raise HTTPException(status_code=403, detail="Forbidden")


def _cleanup_media(godown_id: str, camera_id: str, keep_run_id: Optional[str] = None) -> None:
    snapshots_root = Path(__file__).resolve().parents[3] / "data" / "snapshots" / godown_id
    if snapshots_root.exists():
        for run_dir in snapshots_root.iterdir():
            if not run_dir.is_dir():
                continue
            if keep_run_id and run_dir.name == keep_run_id:
                continue
            cam_dir = run_dir / camera_id
            if cam_dir.exists():
                shutil.rmtree(cam_dir, ignore_errors=True)

    annotated_root = Path(__file__).resolve().parents[3] / "data" / "annotated" / godown_id
    if annotated_root.exists():
        for run_dir in annotated_root.iterdir():
            if not run_dir.is_dir():
                continue
            if keep_run_id and run_dir.name == keep_run_id:
                continue
            for suffix in (".mp4", "_latest.jpg"):
                target = run_dir / f"{camera_id}{suffix}"
                if target.exists():
                    try:
                        target.unlink()
                    except Exception:
                        pass


def _set_camera_source(
    *,
    godown_id: str,
    camera_id: str,
    source_type: str,
    source_path: Optional[str] = None,
    source_run_id: Optional[str] = None,
) -> None:
    with SessionLocal() as db:
        camera = (
            db.query(Camera)
            .filter(Camera.godown_id == godown_id, Camera.id == camera_id)
            .first()
        )
        if not camera:
            return
        camera.source_type = source_type
        if source_type == "test":
            camera.source_path = source_path
            camera.source_run_id = source_run_id
        else:
            camera.source_path = None
            camera.source_run_id = None
        db.add(camera)
        db.commit()


@router.post("")
async def upload_test_run(
    file: UploadFile = File(...),
    godown_id: str = Form(...),
    camera_id: str = Form(...),
    zone_id: Optional[str] = Form(None),
    run_name: Optional[str] = Form(None),
    request=Depends(enforce_upload_limit),
    user: UserContext = Depends(get_current_user),
) -> dict:
    if not file:
        raise HTTPException(status_code=400, detail="Missing file")
    if not _can_access_godown(user, godown_id):
        raise HTTPException(status_code=403, detail="Forbidden")

    def _write_video(dest):
        copy_upload_file(file, dest)

    meta = create_test_run(
        godown_id=godown_id,
        camera_id=camera_id,
        zone_id=zone_id,
        run_name=run_name,
        write_video=_write_video,
    )
    _cleanup_media(godown_id, camera_id, keep_run_id=meta.get("run_id"))
    try:
        with SessionLocal() as db:
            (
                db.query(Alert)
                .filter(
                    Alert.status == "OPEN",
                    Alert.godown_id == godown_id,
                    Alert.camera_id == camera_id,
                )
                .update({"status": "CLOSED"})
            )
            db.commit()
    except Exception:
        pass
    return meta


@router.get("")
def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    user: UserContext = Depends(get_current_user),
) -> dict:
    page_size = clamp_page_size(page_size)
    items = list_test_runs()
    if not _is_admin(user):
        items = [r for r in items if _can_access_godown(user, str(r.get("godown_id") or ""))]
    total = len(items)
    start = max((page - 1) * page_size, 0)
    end = start + page_size
    return {"items": items[start:end], "total": total, "page": page, "page_size": page_size}


@router.get("/{run_id}")
def get_run(run_id: str, user: UserContext = Depends(get_current_user)) -> dict:
    run = get_test_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    _assert_run_access(user, run)
    run.setdefault("events_count", None)
    return run


@router.post("/{run_id}/activate")
def activate_run(run_id: str, user: UserContext = Depends(get_current_user)) -> dict:
    run = get_test_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    _assert_run_access(user, run)
    saved_path = run.get("saved_path")
    if not saved_path or not Path(saved_path).exists():
        # keep system safe: ensure live mode
        override_str = None
        try:
            override_path = write_edge_override(run, mode="live")
            override_str = str(override_path.resolve())
        except Exception:
            pass

        missing_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        update_test_run(
            run_id,
            {
                "status": "MISSING_VIDEO",
                "deactivated_at": missing_at,
                "deactivated_reason": "VIDEO_MISSING",
                **({"override_path": override_str} if override_str else {}),
            },
        )
        try:
            _set_camera_source(
                godown_id=str(run["godown_id"]),
                camera_id=str(run["camera_id"]),
                source_type="live",
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=409,
            detail="Test video missing. Upload again to activate.",
        )
    override_path = write_edge_override(run, mode="test")
    activated_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    try:
        _set_camera_source(
            godown_id=str(run["godown_id"]),
            camera_id=str(run["camera_id"]),
            source_type="test",
            source_path=str(saved_path),
            source_run_id=str(run["run_id"]),
        )
    except Exception:
        pass

    # DEACTIVATE others for the same camera
    all_runs = list_test_runs()
    for existing in all_runs:
        if (
            existing["run_id"] != run_id
            and existing["godown_id"] == run["godown_id"]
            and existing["camera_id"] == run["camera_id"]
            and existing["status"] == "ACTIVE"
        ):
            update_test_run(
                existing["run_id"],
                {
                    "status": "DEACTIVATED",
                    "deactivated_at": activated_at,
                    "deactivated_reason": "SUPERSEDED",
                },
            )

    updated = update_test_run(
        run_id,
        {
            "status": "ACTIVE",
            "override_path": str(override_path.resolve()),
            "activated_at": activated_at,
        },
    )
    try:
        with SessionLocal() as db:
            (
                db.query(Alert)
                .filter(
                    Alert.status == "OPEN",
                    Alert.alert_type == "CAMERA_HEALTH_ISSUE",
                    Alert.godown_id == run["godown_id"],
                    Alert.camera_id == run["camera_id"],
                )
                .update({"status": "CLOSED"})
            )
            db.commit()
    except Exception:
        pass
    return {"run": updated, "override_path": str(override_path.resolve()), "status": "ACTIVE"}


@router.post("/{run_id}/deactivate")
def deactivate_run(run_id: str, user: UserContext = Depends(get_current_user)) -> dict:
    run = get_test_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    _assert_run_access(user, run)
    override_path = write_edge_override(run, mode="live")
    try:
        _set_camera_source(
            godown_id=str(run["godown_id"]),
            camera_id=str(run["camera_id"]),
            source_type="live",
        )
    except Exception:
        pass
    deactivated_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    updated = update_test_run(
        run_id,
        {
            "status": "DEACTIVATED",
            "override_path": str(override_path.resolve()),
            "deactivated_at": deactivated_at,
        },
    )
    return {"run": updated, "override_path": str(override_path.resolve()), "status": "DEACTIVATED"}


@router.delete("/{run_id}")
def delete_run(run_id: str, user: UserContext = Depends(get_current_user)) -> dict:
    run = get_test_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    _assert_run_access(user, run)

    # IMPORTANT: force edge back to live before deleting
    try:
        write_edge_override(run, mode="live")
    except Exception:
        pass
    try:
        _set_camera_source(
            godown_id=str(run["godown_id"]),
            camera_id=str(run["camera_id"]),
            source_type="live",
        )
    except Exception:
        pass

    ok = delete_test_run(run_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete test run")
    return {"status": "DELETED", "run_id": run_id}


@router.get("/{run_id}/stream/{camera_id}")
def stream_annotated(
    run_id: str,
    camera_id: str,
    user: UserContext = Depends(get_current_user),
) -> StreamingResponse:
    run = get_test_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    _assert_run_access(user, run)
    godown_id = run["godown_id"]
    annotated_root = Path(__file__).resolve().parents[3] / "data" / "annotated"
    latest_path = annotated_root / godown_id / run_id / f"{camera_id}_latest.jpg"

    def _frame_iter():
        while True:
            if latest_path.exists():
                try:
                    data = latest_path.read_bytes()
                    yield (
                        b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                        + str(len(data)).encode()
                        + b"\r\n\r\n"
                        + data
                        + b"\r\n"
                    )
                except Exception:
                    pass
            time.sleep(0.2)

    return StreamingResponse(
        _frame_iter(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@router.get("/{run_id}/snapshots/{camera_id}")
def list_snapshots(
    run_id: str,
    camera_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1),
    user: UserContext = Depends(get_current_user),
) -> dict:
    page_size = clamp_page_size(page_size)
    run = get_test_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    _assert_run_access(user, run)
    godown_id = run["godown_id"]
    snapshots_root = Path(__file__).resolve().parents[3] / "data" / "snapshots"
    snapshot_dir = snapshots_root / godown_id / run_id / camera_id
    if not snapshot_dir.exists():
        return {"items": [], "page": page, "page_size": page_size, "total": 0}
    files = sorted(snapshot_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
    total = len(files)
    start = max((page - 1) * page_size, 0)
    end = start + page_size
    files = files[start:end]
    items = [
        f"/media/snapshots/{godown_id}/{run_id}/{camera_id}/{f.name}"
        for f in files
    ]
    return {"items": items, "page": page, "page_size": page_size, "total": total}
