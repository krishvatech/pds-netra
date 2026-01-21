"""
Edge override loader for test mode video sources.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class EdgeOverrideManager:
    """Loads and caches edge override file for test runs."""

    def __init__(self, path: Optional[str], refresh_interval: int = 5) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.path = Path(path).expanduser() if path else None
        self.refresh_interval = refresh_interval
        self._last_checked = 0.0
        self._last_mtime: Optional[float] = None
        self._data: Optional[Dict[str, Any]] = None

    def _load(self) -> None:
        if self.path is None:
            self._data = None
            return
        if not self.path.exists():
            self._data = None
            self._last_mtime = None
            return
        try:
            mtime = self.path.stat().st_mtime
            if self._last_mtime is not None and mtime == self._last_mtime:
                return
            with self.path.open("r", encoding="utf-8") as f:
                self._data = json.load(f)
            self._last_mtime = mtime
        except Exception as exc:
            self.logger.warning("Failed to load override file %s: %s", self.path, exc)
            self._data = None

    def _refresh_if_needed(self) -> None:
        now = time.monotonic()
        if now - self._last_checked < self.refresh_interval:
            return
        self._last_checked = now
        self._load()

    def get_override(self) -> Optional[Dict[str, Any]]:
        self._refresh_if_needed()
        return self._data

    def get_camera_source(
        self,
        camera_id: str,
        default_source: str,
    ) -> Tuple[str, str, Optional[str]]:
        data = self.get_override()
        if not data or data.get("mode") != "test":
            return default_source, "live", None
        overrides = data.get("camera_overrides") or {}
        cam_override = overrides.get(camera_id)
        if not cam_override:
            return default_source, "live", None
        if cam_override.get("source_type") == "file" and cam_override.get("path"):
            return str(cam_override["path"]), "test", data.get("active_run_id")
        return default_source, "live", None
