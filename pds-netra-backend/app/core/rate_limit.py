"""Basic in-memory rate limiter (per-process token bucket)."""

from __future__ import annotations

import hashlib
import os
import threading
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException, Request


def _env_bool(name: str, default: str = "") -> Optional[bool]:
    raw = os.getenv(name)
    if raw is None:
        return None
    val = raw.strip().lower()
    if val in {"1", "true", "yes"}:
        return True
    if val in {"0", "false", "no"}:
        return False
    return None


def _get_app_env() -> str:
    return (os.getenv("PDS_ENV") or os.getenv("APP_ENV") or "dev").strip().lower()


def rate_limit_enabled() -> bool:
    explicit = _env_bool("RATE_LIMIT_ENABLED")
    if explicit is not None:
        return explicit
    return _get_app_env() == "prod"


def _get_rps() -> float:
    raw = os.getenv("RATE_LIMIT_RPS", "5")
    try:
        val = float(raw)
    except Exception:
        val = 5.0
    return max(val, 0.1)


def _get_burst() -> int:
    raw = os.getenv("RATE_LIMIT_BURST", "20")
    try:
        val = int(raw)
    except Exception:
        val = 20
    return max(val, 1)


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    if not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    return token or None


def _path_group(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
        return f"/api/v1/{parts[2]}"
    if len(parts) >= 1:
        return f"/{parts[0]}"
    return "/"


@dataclass
class Bucket:
    tokens: float
    last_ts: float


class TokenBucketLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[str, Bucket] = {}

    def allow(self, key: str, *, rps: float, burst: int) -> tuple[bool, float]:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = Bucket(tokens=float(burst), last_ts=now)
                self._buckets[key] = bucket
            # Refill
            elapsed = max(0.0, now - bucket.last_ts)
            bucket.tokens = min(float(burst), bucket.tokens + elapsed * rps)
            bucket.last_ts = now
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True, 0.0
            # Not enough tokens
            needed = 1.0 - bucket.tokens
            retry_after = needed / rps if rps > 0 else 1.0
            return False, max(retry_after, 0.1)


_limiter = TokenBucketLimiter()


def rate_limit_dependency(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> None:
    if not rate_limit_enabled():
        return

    rps = _get_rps()
    burst = _get_burst()

    token = _extract_bearer_token(authorization)
    if token:
        ident = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    else:
        client = request.client.host if request.client else "unknown"
        ident = client

    group = _path_group(request.url.path)
    key = f"{ident}:{group}"

    allowed, retry_after = _limiter.allow(key, rps=rps, burst=burst)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too Many Requests",
            headers={"Retry-After": str(int(retry_after))},
        )
