"""
Live camera streaming endpoints.
"""

from __future__ import annotations

from pathlib import Path
import os
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from ...core.pagination import clamp_page_size
from ...core.db import get_db
from ...models.godown import Camera
from sqlalchemy.orm import Session


router = APIRouter(prefix="/api/v1/live", tags=["live"])

def _live_root() -> Path:
    return Path(os.getenv("PDS_LIVE_DIR", str(Path(__file__).resolve().parents[3] / "data" / "live"))).expanduser()

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
    latest_path = live_root / godown_id / f"{camera_id}_latest.jpg"
    if not latest_path.parent.exists():
        raise HTTPException(status_code=404, detail="Live feed not available")

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


@router.get("/frame/{godown_id}/{camera_id}")
def latest_frame(godown_id: str, camera_id: str) -> FileResponse:
    live_root = _live_root()
    latest_path = live_root / godown_id / f"{camera_id}_latest.jpg"
    if not latest_path.exists():
        raise HTTPException(status_code=404, detail="Live frame not available")
    return FileResponse(
        latest_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
