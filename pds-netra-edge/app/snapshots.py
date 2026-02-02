"""
Snapshot writer for event images.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    import cv2  # type: ignore
except ImportError:
    cv2 = None  # type: ignore


class SnapshotWriter:
    """Writes event snapshots to disk and returns URL/path."""

    def __init__(self, base_dir: str, base_url: Optional[str] = None) -> None:
        self.base_dir = Path(base_dir).expanduser()
        self.base_url = base_url.rstrip("/") if base_url else None

    def save(
        self,
        frame,
        *,
        godown_id: str,
        camera_id: str,
        event_id: str,
        timestamp_utc: str,
    ) -> Optional[str]:
        if cv2 is None:
            return None
        date_part = timestamp_utc.split("T")[0] if "T" in timestamp_utc else "unknown"
        rel_dir = Path(godown_id) / camera_id / date_part
        out_dir = self.base_dir / rel_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{event_id}.jpg"
        out_path = out_dir / filename
        try:
            cv2.imwrite(str(out_path), frame)
        except Exception:
            return None
        if self.base_url:
            return f"{self.base_url}/{rel_dir.as_posix()}/{filename}"
        return str(out_path.resolve())


def default_snapshot_writer() -> Optional[SnapshotWriter]:
    base_dir = os.getenv("EDGE_SNAPSHOT_DIR")
    if not base_dir:
        # Default to backend data/snapshots folder if present
        base_dir = str(Path(__file__).resolve().parents[2] / "pds-netra-backend" / "data" / "snapshots")
    base_url = os.getenv("EDGE_SNAPSHOT_BASE_URL", "http://127.0.0.1:8001/media/snapshots")
    return SnapshotWriter(base_dir=base_dir, base_url=base_url)
