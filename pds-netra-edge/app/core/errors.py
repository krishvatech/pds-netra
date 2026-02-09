"""
Shared error-handling helpers for edge services.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")


def _format_extra(extra: dict | None) -> str:
    if not extra:
        return ""
    parts: list[str] = []
    for key, value in extra.items():
        if value is None:
            continue
        parts.append(f"{key}={value}")
    return f" {' '.join(parts)}" if parts else ""


def log_exception(logger: logging.Logger, msg: str, *, extra: dict | None = None, exc: Exception | None = None) -> None:
    """
    Log an exception with context. Uses logger.exception for stack traces.
    """
    suffix = _format_extra(extra)
    if exc is not None:
        logger.error(f"{msg}{suffix}: {exc}", exc_info=exc)
        return
    logger.exception(f"{msg}{suffix}")


def safe_json_load(path: str | Path, default: T, *, logger: logging.Logger | None = None, context: dict | None = None) -> T:
    """
    Best-effort JSON load with logging. Returns default on failure.
    """
    try:
        with Path(path).open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        if logger:
            log_exception(logger, "JSON load failed", extra={"path": str(path), **(context or {})}, exc=exc)
        return default


def safe_json_dump_atomic(
    path: str | Path,
    data: Any,
    *,
    logger: logging.Logger | None = None,
    context: dict | None = None,
    indent: int = 2,
) -> bool:
    """
    Atomically write JSON to disk. Returns True on success, False otherwise.
    """
    target = Path(path)
    tmp_path: Optional[Path] = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=target.name, suffix=".tmp", dir=str(target.parent))
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp_path), str(target))
        return True
    except Exception as exc:
        if logger:
            log_exception(
                logger,
                "JSON atomic write failed",
                extra={"path": str(target), **(context or {})},
                exc=exc,
            )
        return False
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception as exc:
                logging.getLogger("errors").warning("Failed to cleanup temp JSON file %s: %s", tmp_path, exc)


def guarded_call(
    name: str,
    fn: Callable[[], T],
    *,
    fallback: T | None = None,
    logger: logging.Logger | None = None,
    context: dict | None = None,
) -> T | None:
    """
    Execute fn with logging on failure. Returns fallback if provided.
    """
    try:
        return fn()
    except Exception as exc:
        if logger:
            log_exception(logger, f"{name} failed", extra=context or {}, exc=exc)
        return fallback
