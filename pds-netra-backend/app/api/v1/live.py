"""
Live camera streaming endpoints.
"""

from __future__ import annotations

from pathlib import Path
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, FileResponse


router = APIRouter(prefix="/api/v1/live", tags=["live"])


@router.get("/{godown_id}")
def list_live_cameras(godown_id: str) -> dict:
    live_root = Path(__file__).resolve().parents[3] / "data" / "live"
    godown_dir = live_root / godown_id
    if not godown_dir.exists():
        return {"godown_id": godown_id, "cameras": []}
    cameras = []
    for item in godown_dir.glob("*_latest.jpg"):
        camera_id = item.name.replace("_latest.jpg", "")
        cameras.append(camera_id)
    return {"godown_id": godown_id, "cameras": sorted(cameras)}


@router.get("/{godown_id}/{camera_id}")
def stream_live(godown_id: str, camera_id: str) -> StreamingResponse:
    live_root = Path(__file__).resolve().parents[3] / "data" / "live"
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
    live_root = Path(__file__).resolve().parents[3] / "data" / "live"
    latest_path = live_root / godown_id / f"{camera_id}_latest.jpg"
    if not latest_path.exists():
        raise HTTPException(status_code=404, detail="Live frame not available")
    return FileResponse(
        latest_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
