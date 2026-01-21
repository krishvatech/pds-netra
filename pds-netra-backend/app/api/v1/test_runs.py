"""
Test run upload and activation endpoints.
"""

from __future__ import annotations

import shutil
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ...services.test_runs import (
    create_test_run,
    get_test_run,
    list_test_runs,
    update_test_run,
    write_edge_override,
)


router = APIRouter(prefix="/api/v1/test-runs", tags=["test-runs"])


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
