"""
Test run storage utilities for PDS Netra backend.

Stores uploaded MP4 files and lightweight metadata on local disk for PoC usage.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional


@dataclass
class TestRunPaths:
    run_dir: Path
    video_path: Path
    meta_path: Path
    config_path: Path


def _base_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return _base_dir() / "data"


def uploads_dir() -> Path:
    return data_dir() / "uploads"


def overrides_dir() -> Path:
    return data_dir() / "edge_overrides"


def _ensure_dirs() -> None:
    uploads_dir().mkdir(parents=True, exist_ok=True)
    overrides_dir().mkdir(parents=True, exist_ok=True)


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _paths_for_run(godown_id: str, run_id: str, camera_id: str) -> TestRunPaths:
    run_dir = uploads_dir() / godown_id / run_id
    video_path = run_dir / f"{camera_id}.mp4"
    meta_path = run_dir / "test_run.json"
    config_path = run_dir / "test_run_config.json"
    return TestRunPaths(
        run_dir=run_dir,
        video_path=video_path,
        meta_path=meta_path,
        config_path=config_path,
    )


def create_test_run(
    *,
    godown_id: str,
    camera_id: str,
    zone_id: Optional[str],
    run_name: Optional[str],
    write_video,
) -> Dict[str, Any]:
    _ensure_dirs()
    run_id = uuid.uuid4().hex
    paths = _paths_for_run(godown_id, run_id, camera_id)
    paths.run_dir.mkdir(parents=True, exist_ok=True)

    with paths.video_path.open("wb") as f:
        write_video(f)

    created_at = _utc_now()
    meta = {
        "run_id": run_id,
        "godown_id": godown_id,
        "camera_id": camera_id,
        "zone_id": zone_id,
        "run_name": run_name,
        "status": "UPLOADED",
        "created_at": created_at,
        "updated_at": created_at,
        "saved_path": str(paths.video_path.resolve()),
        "config_path": str(paths.config_path.resolve()),
        "override_path": None,
    }
    with paths.meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    config = {
        "run_id": run_id,
        "godown_id": godown_id,
        "camera_id": camera_id,
        "zone_id": zone_id,
        "run_name": run_name,
        "saved_path": str(paths.video_path.resolve()),
        "created_at": created_at,
    }
    with paths.config_path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    return meta


def list_test_runs() -> List[Dict[str, Any]]:
    _ensure_dirs()
    runs: List[Dict[str, Any]] = []
    for godown_dir in uploads_dir().iterdir():
        if not godown_dir.is_dir():
            continue
        for run_dir in godown_dir.iterdir():
            if not run_dir.is_dir():
                continue
            meta_path = run_dir / "test_run.json"
            if not meta_path.exists():
                continue
            try:
                with meta_path.open("r", encoding="utf-8") as f:
                    run = json.load(f)
                run = _apply_completion_status(run)
                runs.append(run)
            except Exception:
                continue
    runs.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return runs


def _find_run_dir(run_id: str) -> Optional[Path]:
    if not uploads_dir().exists():
        return None
    for godown_dir in uploads_dir().iterdir():
        candidate = godown_dir / run_id
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def get_test_run(run_id: str) -> Optional[Dict[str, Any]]:
    _ensure_dirs()
    run_dir = _find_run_dir(run_id)
    if not run_dir:
        return None
    meta_path = run_dir / "test_run.json"
    if not meta_path.exists():
        return None
    try:
        with meta_path.open("r", encoding="utf-8") as f:
            run = json.load(f)
        return _apply_completion_status(run)
    except Exception:
        return None


def update_test_run(run_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    run = get_test_run(run_id)
    if run is None:
        return None
    run.update(updates)
    run["updated_at"] = _utc_now()
    run_dir = _find_run_dir(run_id)
    if run_dir is None:
        return None
    meta_path = run_dir / "test_run.json"
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(run, f, indent=2)
    return run


def write_edge_override(run: Dict[str, Any], *, mode: str) -> Path:
    _ensure_dirs()
    godown_id = run["godown_id"]
    camera_id = run["camera_id"]
    saved_path = run["saved_path"]
    override_path = overrides_dir() / f"{godown_id}.json"
    if mode == "test":
        payload = {
            "mode": "test",
            "godown_id": godown_id,
            "camera_overrides": {
                camera_id: {"source_type": "file", "path": saved_path}
            },
            "active_run_id": run["run_id"],
        }
    else:
        payload = {
            "mode": "live",
            "godown_id": godown_id,
            "camera_overrides": {},
            "active_run_id": None,
        }
    with override_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return override_path


def delete_test_run(run_id: str) -> bool:
    run = get_test_run(run_id)
    if run is None:
        return False
    godown_id = run.get("godown_id")
    if godown_id:
        run_dir = uploads_dir() / godown_id / run_id
        annotated_dir = data_dir() / "annotated" / godown_id / run_id
        snapshots_dir = data_dir() / "snapshots" / godown_id / run_id
        for path in (run_dir, annotated_dir, snapshots_dir):
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
    return True


def _apply_completion_status(run: Dict[str, Any]) -> Dict[str, Any]:
    if run.get("status") == "COMPLETED":
        return run
    annotated_dir = data_dir() / "annotated" / run.get("godown_id", "") / run.get("run_id", "")
    marker = annotated_dir / "completed.json"
    if marker.exists():
        try:
            completed = json.loads(marker.read_text(encoding="utf-8"))
            run = update_test_run(
                run["run_id"],
                {
                    "status": "COMPLETED",
                    "completed_at": completed.get("completed_at"),
                },
            ) or run
        except Exception:
            return run
    return run
