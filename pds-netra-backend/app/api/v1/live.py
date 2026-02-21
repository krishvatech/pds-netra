"""
Live camera streaming endpoints.
"""

from __future__ import annotations

from pathlib import Path
import os
import time
from datetime import datetime, timezone
import threading
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from ...core.pagination import clamp_page_size
from ...core.db import get_db
from ...models.godown import Camera
from ...services.live_frames import enforce_single_live_frame
from sqlalchemy.orm import Session


router = APIRouter(prefix="/api/v1/live", tags=["live"])
logger = logging.getLogger("live")
_stale_log_lock = threading.Lock()
_stale_log_last: dict[tuple[str, str], float] = {}


def _live_root() -> Path:
    return Path(os.getenv("PDS_LIVE_DIR", str(Path(__file__).resolve().parents[3] / "data" / "live"))).expanduser()


def _frame_meta(frame_path: Path) -> dict:
    if not frame_path.exists():
        return {
            "available": False,
            "captured_at_utc": None,
            "age_seconds": None,
        }
    stat = frame_path.stat()
    captured_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    age_seconds = max(0.0, (datetime.now(timezone.utc) - captured_at).total_seconds())
    return {
        "available": True,
        "captured_at_utc": captured_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "age_seconds": round(age_seconds, 3),
    }


def _env_true(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


def _stale_threshold_sec() -> float:
    raw = os.getenv("PDS_LIVE_STALE_THRESHOLD_SEC", "30")
    try:
        value = float(raw)
        if value >= 0:
            return value
    except Exception:
        pass
    return 30.0


def _stale_log_cooldown_sec() -> float:
    raw = os.getenv("PDS_LIVE_STALE_LOG_COOLDOWN_SEC", "60")
    try:
        value = float(raw)
        if value >= 1:
            return value
    except Exception:
        pass
    return 60.0


def _is_stale(age_seconds: float | None, threshold_seconds: float) -> bool:
    if age_seconds is None:
        return False
    return age_seconds >= threshold_seconds


def _stream_poll_interval_sec() -> float:
    raw = os.getenv("PDS_LIVE_STREAM_POLL_SEC", "0.2")
    try:
        value = float(raw)
        if value >= 0.05:
            return value
    except Exception:
        pass
    return 0.2


def _mjpeg_frame(data: bytes) -> bytes:
    return (
        b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
        + str(len(data)).encode()
        + b"\r\n\r\n"
        + data
        + b"\r\n"
    )


def _maybe_log_stale_frame(godown_id: str, camera_id: str, *, age_seconds: float, threshold_seconds: float) -> None:
    if not _env_true("PDS_LIVE_STALE_LOG_ENABLED", "false"):
        return
    now_mono = time.monotonic()
    cooldown = _stale_log_cooldown_sec()
    key = (godown_id, camera_id)
    with _stale_log_lock:
        last = _stale_log_last.get(key)
        if last is not None and (now_mono - last) < cooldown:
            return
        _stale_log_last[key] = now_mono
    logger.warning(
        "Live frame stale godown=%s camera=%s age_seconds=%.3f threshold_seconds=%.3f",
        godown_id,
        camera_id,
        age_seconds,
        threshold_seconds,
    )

@router.get("/{godown_id}")
def list_live_cameras(
    godown_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
) -> dict:
    page_size = clamp_page_size(page_size)
    cameras_sorted = [
        row[0]
        for row in (
            db.query(Camera.id)
            .filter(Camera.godown_id == godown_id, Camera.is_active.is_(True))
            .order_by(Camera.id.asc())
            .all()
        )
    ]
    total = len(cameras_sorted)
    start = max((page - 1) * page_size, 0)
    end = start + page_size
    return {
        "godown_id": godown_id,
        "cameras": cameras_sorted[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{godown_id}/{camera_id}")
def stream_live(godown_id: str, camera_id: str) -> StreamingResponse:
    live_root = _live_root()
    latest_path = enforce_single_live_frame(live_root, godown_id, camera_id)
    if not latest_path.parent.exists():
        raise HTTPException(status_code=404, detail="Live feed not available")

    def _frame_iter():
        poll_sec = _stream_poll_interval_sec()
        last_sig: tuple[int, int] | None = None
        while True:
            try:
                stat = latest_path.stat()
                sig = (stat.st_mtime_ns, stat.st_size)
                if sig != last_sig:
                    data = latest_path.read_bytes()
                    if data:
                        yield _mjpeg_frame(data)
                    last_sig = sig
            except FileNotFoundError:
                pass
            except Exception:
                pass
            time.sleep(poll_sec)

    return StreamingResponse(
        _frame_iter(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@router.get("/frame/{godown_id}/{camera_id}")
def latest_frame(godown_id: str, camera_id: str) -> FileResponse:
    live_root = _live_root()
    latest_path = enforce_single_live_frame(live_root, godown_id, camera_id)
    if not latest_path.exists():
        raise HTTPException(status_code=404, detail="Live frame not available")
    meta = _frame_meta(latest_path)
    threshold_seconds = _stale_threshold_sec()
    stale = _is_stale(meta["age_seconds"], threshold_seconds)
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    if meta["captured_at_utc"] is not None:
        headers["X-Frame-Captured-At"] = str(meta["captured_at_utc"])
    if meta["age_seconds"] is not None:
        headers["X-Frame-Age-Seconds"] = f"{meta['age_seconds']:.3f}"
    headers["X-Frame-Stale"] = "1" if stale else "0"
    headers["X-Frame-Stale-Threshold-Seconds"] = f"{threshold_seconds:.3f}"
    if stale and meta["age_seconds"] is not None:
        _maybe_log_stale_frame(
            godown_id,
            camera_id,
            age_seconds=float(meta["age_seconds"]),
            threshold_seconds=threshold_seconds,
        )
    return FileResponse(
        latest_path,
        media_type="image/jpeg",
        headers=headers,
    )


@router.get("/frame-meta/{godown_id}/{camera_id}")
def latest_frame_meta(godown_id: str, camera_id: str) -> dict:
    live_root = _live_root()
    latest_path = enforce_single_live_frame(live_root, godown_id, camera_id)
    meta = _frame_meta(latest_path)
    threshold_seconds = _stale_threshold_sec()
    stale = _is_stale(meta["age_seconds"], threshold_seconds)
    if stale and meta["age_seconds"] is not None:
        _maybe_log_stale_frame(
            godown_id,
            camera_id,
            age_seconds=float(meta["age_seconds"]),
            threshold_seconds=threshold_seconds,
        )
    return {
        "godown_id": godown_id,
        "camera_id": camera_id,
        "stale": stale,
        "stale_threshold_seconds": threshold_seconds,
        **meta,
    }
