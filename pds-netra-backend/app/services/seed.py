"""
Seed godowns and cameras for PoC usage.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

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
            camera = Camera(
                id=cam_id,
                godown_id=godown_id,
                label=cam.get("label"),
                role=cam.get("role"),
                zones_json=cam.get("zones_json"),
            )
            db.add(camera)
        count += 1
    db.commit()
    return count
