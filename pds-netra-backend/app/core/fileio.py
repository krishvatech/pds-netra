"""
Shared file I/O helpers with atomic writes and optional locking.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")

logger = logging.getLogger("fileio")


def read_json_file(path: Path, default: T) -> T:
    """
    Read JSON from path. Returns default on missing/invalid data.
    """
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Failed to read JSON path=%s err=%s", path, exc)
        return default


def write_json_atomic(path: Path, data: Any) -> None:
    """
    Atomically write JSON to disk with fsync on file and directory.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Optional[Path] = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(path.parent))
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp_path), str(path))
        try:
            dir_fd = os.open(str(path.parent), os.O_DIRECTORY)
        except Exception:
            dir_fd = None
        if dir_fd is not None:
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception as exc:
                logger.warning("Failed to cleanup temp JSON path=%s err=%s", tmp_path, exc)


def locked_json_update(path: Path, update_fn: Callable[[list], list]) -> list:
    """
    Lock, read JSON list, apply update_fn, write atomically.
    Returns updated list.
    """
    lock_supported = True
    try:
        import fcntl  # type: ignore
    except Exception:
        fcntl = None  # type: ignore
        lock_supported = False

    if not lock_supported:
        logger.warning("File lock not available; using atomic write without lock path=%s", path)
        current = read_json_file(path, [])
        if not isinstance(current, list):
            current = []
        updated = update_fn(current)
        write_json_atomic(path, updated)
        return updated

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            current = read_json_file(path, [])
            if not isinstance(current, list):
                current = []
            updated = update_fn(current)
            write_json_atomic(path, updated)
            return updated
        finally:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except Exception as exc:
                logger.warning("Failed to release file lock path=%s err=%s", path, exc)
