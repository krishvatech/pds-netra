"""
Test run upload and activation endpoints.
"""

from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ...core.db import SessionLocal
from ...models.event import Alert
from ...services.test_runs import (
    create_test_run,
    delete_test_run,
    get_test_run,
    list_test_runs,
    update_test_run,
    write_edge_override,
)

router = APIRouter(prefix="/api/v1/test-runs", tags=["test-runs"])


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


@router.post("")
async def upload_test_run(
    file: UploadFile = File(...),
    godown_id: str = Form(...),
    camera_id: str = Form(...),
    zone_id: Optional[str] = Form(None),
    run_name: Optional[str] = Form(None),
) -> dict:
    if not file:
        raise HTTPException(status_code=400, detail="Missing file")

    def _write_video(dest):
        shutil.copyfileobj(file.file, dest)

    meta = create_test_run(
        godown_id=godown_id,
        camera_id=camera_id,
        zone_id=zone_id,
        run_name=run_name,
        write_video=_write_video,
    )
    _cleanup_media(godown_id, camera_id, keep_run_id=meta.get("run_id"))

    # Close open alerts for this camera (best-effort)
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
def list_runs() -> list[dict]:
    return list_test_runs()


@router.get("/{run_id}")
def get_run(run_id: str) -> dict:
    run = get_test_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    run.setdefault("events_count", None)
    return run


@router.post("/{run_id}/activate")
def activate_run(run_id: str) -> dict:
    run = get_test_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")

    override_path = write_edge_override(run, mode="test")
    activated_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    updated = update_test_run(
        run_id,
        {
            "status": "ACTIVE",
            "override_path": str(override_path.resolve()),
            "activated_at": activated_at,
        },
    )

    # Close camera health alerts for this camera (best-effort)
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
def deactivate_run(run_id: str) -> dict:
    run = get_test_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")

    override_path = write_edge_override(run, mode="live")
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
def delete_run(run_id: str) -> dict:
    run = get_test_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    ok = delete_test_run(run_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete test run")
    return {"status": "DELETED", "run_id": run_id}


def _read_bytes_with_retry(path: Path, retries: int = 5, delay: float = 0.02) -> Optional[bytes]:
    """
    Windows fix: the Edge process may be replacing/writing the file while the Backend reads it.
    That can raise PermissionError / WinError 5. Retry a few times.
    """
    for _ in range(max(1, retries)):
        try:
            return path.read_bytes()
        except FileNotFoundError:
            time.sleep(delay)
        except PermissionError:
            time.sleep(delay)
        except OSError:
            # e.g., transient sharing violation, partial write, etc.
            time.sleep(delay)
        except Exception:
            time.sleep(delay)
    return None


@router.get("/{run_id}/stream/{camera_id}")
def stream_annotated(run_id: str, camera_id: str) -> StreamingResponse:
    run = get_test_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")

    godown_id = run["godown_id"]
    annotated_root = Path(__file__).resolve().parents[3] / "data" / "annotated"
    latest_path = annotated_root / godown_id / run_id / f"{camera_id}_latest.jpg"

    def _frame_iter():
        boundary = b"--frame\r\n"
        last_good: Optional[bytes] = None
        last_mtime: Optional[float] = None

        # If multiple tabs open the stream, it increases read/write contention on Windows.
        # The retry + last_good logic below makes the stream stable anyway.
        while True:
            try:
                if latest_path.exists():
                    try:
                        mtime = latest_path.stat().st_mtime
                    except Exception:
                        mtime = None

                    # Only attempt to read if changed, or if we have no cached frame yet
                    if (mtime is not None and mtime != last_mtime) or last_good is None:
                        data = _read_bytes_with_retry(latest_path, retries=6, delay=0.02)
                        if data:
                            last_good = data
                            last_mtime = mtime

                if last_good:
                    yield (
                        boundary
                        + b"Content-Type: image/jpeg\r\nContent-Length: "
                        + str(len(last_good)).encode()
                        + b"\r\n\r\n"
                        + last_good
                        + b"\r\n"
                    )
            except Exception:
                # Never kill the stream generator
                pass

            # 5 FPS stream
            time.sleep(0.2)

    return StreamingResponse(
        _frame_iter(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@router.get("/{run_id}/snapshots/{camera_id}")
def list_snapshots(run_id: str, camera_id: str, page: int = 1, page_size: int = 12) -> dict:
    run = get_test_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")

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

    items = [f"/media/snapshots/{godown_id}/{run_id}/{camera_id}/{f.name}" for f in files]
    return {"items": items, "page": page, "page_size": page_size, "total": total}
