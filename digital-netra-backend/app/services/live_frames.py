from __future__ import annotations

from pathlib import Path
from uuid import UUID


def live_latest_path(live_root: str | Path, camera_id: UUID) -> Path:
    root = Path(live_root)
    return root / f"{camera_id}_latest.jpg"


def live_latest_tmp_path(live_root: str | Path, camera_id: UUID) -> Path:
    root = Path(live_root)
    return root / f"{camera_id}_latest.tmp"


def remove_live_frame_artifacts(live_root: str | Path, camera_id: UUID) -> None:
    for path in (live_latest_path(live_root, camera_id), live_latest_tmp_path(live_root, camera_id)):
        try:
            path.unlink()
        except FileNotFoundError:
            continue
