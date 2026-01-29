"""
Seed godowns and cameras for PoC usage.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore

from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.godown import Godown, Camera


def _load_seed(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return []


def seed_godowns(db: Session, seed_path: Path) -> int:
    """
    Seed godowns and cameras if no godowns exist.

    Returns number of godowns inserted.
    """
    existing = db.query(func.count(Godown.id)).scalar() or 0
    if existing > 0:
        return 0
    if not seed_path.exists():
        return 0
    items = _load_seed(seed_path)
    count = 0
    for item in items:
        godown_id = item.get("id")
        if not godown_id:
            continue
        godown = Godown(
            id=godown_id,
            name=item.get("name"),
            district=item.get("district"),
            code=item.get("code"),
        )
        db.add(godown)
        for cam in item.get("cameras", []) or []:
            cam_id = cam.get("id")
            if not cam_id:
                continue
            modules_json = None
            if cam.get("modules") is not None:
                try:
                    modules_json = json.dumps(cam.get("modules"))
                except Exception:
                    modules_json = None
            camera = Camera(
                id=cam_id,
                godown_id=godown_id,
                label=cam.get("label"),
                role=cam.get("role"),
                zones_json=cam.get("zones_json"),
                modules_json=modules_json,
            )
            db.add(camera)
        count += 1
    db.commit()
    return count


def seed_cameras_from_edge_config(db: Session, config_path: Path) -> int:
    """
    Seed cameras from the edge YAML config into the backend DB.

    Returns number of cameras inserted.
    """
    if yaml is None or not config_path.exists():
        return 0
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    godown_id = data.get("godown_id")
    if not godown_id:
        return 0
    godown = db.get(Godown, godown_id)
    if godown is None:
        godown = Godown(id=godown_id, name=godown_id)
        db.add(godown)
        db.commit()
        db.refresh(godown)
    count = 0
    for cam in data.get("cameras", []) or []:
        cam_id = cam.get("id")
        if not cam_id:
            continue
        zones_json = None
        if cam.get("zones") is not None:
            try:
                zones_json = json.dumps(cam.get("zones"))
            except Exception:
                zones_json = None
        modules_json = None
        if cam.get("modules") is not None:
            try:
                modules_json = json.dumps(cam.get("modules"))
            except Exception:
                modules_json = None
        existing = db.get(Camera, cam_id)
        if existing:
            updated = False
            if zones_json is not None and existing.zones_json != zones_json:
                existing.zones_json = zones_json
                updated = True
            if cam.get("rtsp_url") and existing.rtsp_url != cam.get("rtsp_url"):
                existing.rtsp_url = cam.get("rtsp_url")
                updated = True
            if cam.get("label") and existing.label != cam.get("label"):
                existing.label = cam.get("label")
                updated = True
            if cam.get("role") and existing.role != cam.get("role"):
                existing.role = cam.get("role")
                updated = True
            if modules_json is not None and existing.modules_json != modules_json:
                existing.modules_json = modules_json
                updated = True
            if updated:
                db.add(existing)
            continue
        camera = Camera(
            id=cam_id,
            godown_id=godown_id,
            label=cam.get("label") or cam_id,
            role=cam.get("role"),
            rtsp_url=cam.get("rtsp_url"),
            zones_json=zones_json,
            modules_json=modules_json,
        )
        db.add(camera)
        count += 1
    if count:
        db.commit()
    return count
