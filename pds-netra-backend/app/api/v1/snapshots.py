from __future__ import annotations

import os
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from ...core.auth import get_current_user_or_authorized_users_service

router = APIRouter(prefix="/api/v1/snapshots", tags=["snapshots"])
logger = logging.getLogger("snapshots")

def _snapshots_root() -> Path:
    # Use PDS_DATA_DIR if set, otherwise fallback to project-relative data/snapshots
    data_dir = os.getenv("PDS_DATA_DIR")
    if data_dir:
        return Path(data_dir).expanduser() / "snapshots"
    
    # Fallback for Docker/Production
    if Path("/opt/app/data").exists():
        return Path("/opt/app/data/snapshots")
        
    return Path(__file__).resolve().parents[3] / "data" / "snapshots"

@router.post("/{godown_id}/{camera_id}/{date_str}/{filename}")
async def upload_snapshot(
    godown_id: str,
    camera_id: str,
    date_str: str,
    filename: str,
    file: UploadFile = File(...),
    user=Depends(get_current_user_or_authorized_users_service),
) -> dict:
    """Upload a snapshot from edge service."""
    if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
         raise HTTPException(status_code=400, detail="Invalid file type")

    root = _snapshots_root()
    target_dir = root / godown_id / camera_id / date_str
    target_path = target_dir / filename

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        content = await file.read()
        target_path.write_bytes(content)
        
        logger.info("Snapshot uploaded: %s/%s/%s/%s", godown_id, camera_id, date_str, filename)
        
        return {
            "status": "success",
            "path": f"{godown_id}/{camera_id}/{date_str}/{filename}"
        }
    except Exception as e:
        logger.error("Failed to save snapshot %s: %s", target_path, e)
        raise HTTPException(status_code=500, detail="Failed to save snapshot")
