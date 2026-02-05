"""
Helper utilities for managing incident lifecycle timestamps.
"""

from __future__ import annotations

import datetime

from ..models.event import Alert


def _ensure_utc(ts: datetime.datetime) -> datetime.datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=datetime.timezone.utc)
    return ts.astimezone(datetime.timezone.utc)


def touch_detection_timestamp(alert: Alert, timestamp: datetime.datetime | None) -> None:
    if timestamp is None:
        return
    ts = _ensure_utc(timestamp)
    if alert.first_detected_at is None:
        alert.first_detected_at = ts
    alert.last_detection_at = ts


def mark_alert_closed(alert: Alert, timestamp: datetime.datetime | None = None) -> None:
    now = _ensure_utc(timestamp or datetime.datetime.now(datetime.timezone.utc))
    alert.status = "CLOSED"
    alert.closed_at = now
    alert.end_time = now
