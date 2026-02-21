"""
Helpers for enforcing single-file live frame storage per camera.
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
import time
from pathlib import Path


_LOG = logging.getLogger("live_frames")
_CLEANUP_LOCK = threading.Lock()
_LAST_CLEANUP_MONO: dict[tuple[str, str, str], float] = {}
_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


def _cleanup_interval_sec() -> float:
    raw = os.getenv("PDS_LIVE_SINGLE_FRAME_CLEANUP_INTERVAL_SEC", "30")
    try:
        value = float(raw)
        if value >= 0:
            return value
    except Exception:
        pass
    return 30.0


def _should_enforce() -> bool:
    return os.getenv("PDS_LIVE_ENFORCE_SINGLE_FRAME", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def _camera_latest_path(live_root: Path, godown_id: str, camera_id: str) -> Path:
    return live_root / godown_id / f"{camera_id}_latest.jpg"


def _is_image_candidate(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(_IMAGE_SUFFIXES) or name.endswith(".jpg.tmp")


def _collect_legacy_candidates(
    *,
    godown_dir: Path,
    camera_id: str,
    latest_path: Path,
    include_subdirs: bool,
) -> list[Path]:
    files: list[Path] = []
    for ext in _IMAGE_SUFFIXES:
        pattern = f"{camera_id}_*{ext}"
        for path in godown_dir.glob(pattern):
            if path == latest_path or not path.is_file():
                continue
            files.append(path)

    if include_subdirs:
        camera_dir = godown_dir / camera_id
        if camera_dir.exists() and camera_dir.is_dir():
            for path in camera_dir.rglob("*"):
                if path.is_file() and _is_image_candidate(path):
                    files.append(path)

    # de-dup while preserving order
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in files:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def _safe_unlink(path: Path) -> bool:
    try:
        path.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _promote_to_latest(source: Path, latest_path: Path) -> bool:
    try:
        latest_path.parent.mkdir(parents=True, exist_ok=True)
        source.replace(latest_path)
        return True
    except Exception:
        # Cross-device rename fallback.
        try:
            latest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, latest_path)
            source.unlink(missing_ok=True)
            return True
        except Exception:
            _LOG.debug("Failed to promote legacy live frame source=%s target=%s", source, latest_path)
            return False


def enforce_single_live_frame(
    live_root: Path,
    godown_id: str,
    camera_id: str,
    *,
    cleanup_every_sec: float | None = None,
    include_subdirs: bool = True,
) -> Path:
    """
    Ensure a camera has only one live frame file: <camera_id>_latest.jpg.
    """
    latest_path = _camera_latest_path(live_root, godown_id, camera_id)
    if not _should_enforce():
        return latest_path

    interval = _cleanup_interval_sec() if cleanup_every_sec is None else max(0.0, float(cleanup_every_sec))
    key = (str(live_root), godown_id, camera_id)
    now = time.monotonic()
    with _CLEANUP_LOCK:
        last = _LAST_CLEANUP_MONO.get(key)
        if interval > 0 and last is not None and (now - last) < interval:
            return latest_path
        _LAST_CLEANUP_MONO[key] = now

    godown_dir = live_root / godown_id
    if not godown_dir.exists() or not godown_dir.is_dir():
        return latest_path

    candidates = _collect_legacy_candidates(
        godown_dir=godown_dir,
        camera_id=camera_id,
        latest_path=latest_path,
        include_subdirs=include_subdirs,
    )
    if not candidates:
        return latest_path

    promoted = False
    if not latest_path.exists():
        newest: Path | None = None
        newest_mtime = -1
        for path in candidates:
            try:
                mtime = path.stat().st_mtime_ns
            except Exception:
                continue
            if mtime > newest_mtime:
                newest = path
                newest_mtime = mtime
        if newest is not None and _promote_to_latest(newest, latest_path):
            promoted = True
            candidates = [path for path in candidates if path != newest]

    removed = 0
    for path in candidates:
        if _safe_unlink(path):
            removed += 1

    tmp_path = latest_path.with_suffix(latest_path.suffix + ".tmp")
    if _safe_unlink(tmp_path):
        removed += 1

    # Best-effort cleanup for legacy per-camera folder.
    camera_dir = godown_dir / camera_id
    if camera_dir.exists() and camera_dir.is_dir():
        try:
            camera_dir.rmdir()
        except Exception:
            pass

    if removed > 0 or promoted:
        _LOG.info(
            "Live frame cleanup camera=%s godown=%s promoted=%s removed=%s",
            camera_id,
            godown_id,
            promoted,
            removed,
        )
    return latest_path


def remove_live_frame_artifacts(
    live_root: Path,
    godown_id: str,
    camera_id: str,
    *,
    include_latest: bool = True,
    include_subdirs: bool = True,
) -> None:
    """
    Best-effort cleanup for all live artifacts belonging to a camera.
    """
    latest_path = _camera_latest_path(live_root, godown_id, camera_id)
    godown_dir = live_root / godown_id
    if not godown_dir.exists() or not godown_dir.is_dir():
        return

    candidates = _collect_legacy_candidates(
        godown_dir=godown_dir,
        camera_id=camera_id,
        latest_path=latest_path,
        include_subdirs=include_subdirs,
    )
    if include_latest:
        candidates.append(latest_path)
        candidates.append(latest_path.with_suffix(latest_path.suffix + ".tmp"))

    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        _safe_unlink(path)

    camera_dir = godown_dir / camera_id
    if camera_dir.exists() and camera_dir.is_dir():
        try:
            shutil.rmtree(camera_dir, ignore_errors=True)
        except Exception:
            pass
