"""
After-hours policy resolution and evaluation helpers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from ..models.after_hours_policy import AfterHoursPolicy as AfterHoursPolicyModel


def _parse_time(value: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except Exception:
        return time(0, 0)


def _is_time_in_range(now_time: time, start_time: time, end_time: time) -> bool:
    if start_time <= end_time:
        return start_time <= now_time < end_time
    return now_time >= start_time or now_time < end_time


@dataclass
class AfterHoursPolicy:
    day_start: str
    day_end: str
    presence_allowed: bool
    cooldown_seconds: int
    enabled: bool
    timezone: str


def default_policy() -> AfterHoursPolicy:
    try:
        cooldown = int(os.getenv("AFTER_HOURS_ALERT_COOLDOWN_SEC", "120"))
    except Exception:
        cooldown = 120
    return AfterHoursPolicy(
        day_start=os.getenv("AFTER_HOURS_DAY_START", "09:00"),
        day_end=os.getenv("AFTER_HOURS_DAY_END", "19:00"),
        presence_allowed=os.getenv("AFTER_HOURS_PRESENCE_ALLOWED", "false").lower() in {"1", "true", "yes"},
        cooldown_seconds=cooldown,
        enabled=os.getenv("AFTER_HOURS_ENABLED", "true").lower() in {"1", "true", "yes"},
        timezone=os.getenv("AFTER_HOURS_TIMEZONE", "Asia/Kolkata"),
    )


def get_after_hours_policy(db: Session, godown_id: str) -> AfterHoursPolicy:
    row = (
        db.query(AfterHoursPolicyModel)
        .filter(AfterHoursPolicyModel.godown_id == godown_id)
        .first()
    )
    if row:
        return AfterHoursPolicy(
            day_start=row.day_start,
            day_end=row.day_end,
            presence_allowed=bool(row.presence_allowed),
            cooldown_seconds=int(row.cooldown_seconds),
            enabled=bool(row.enabled),
            timezone=row.timezone or "Asia/Kolkata",
        )
    return default_policy()


def is_after_hours(occurred_at: datetime, policy: AfterHoursPolicy) -> bool:
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=ZoneInfo("UTC"))
    try:
        tz = ZoneInfo(policy.timezone)
    except Exception:
        tz = ZoneInfo("UTC")
    local_time = occurred_at.astimezone(tz).timetz()
    start = _parse_time(policy.day_start)
    end = _parse_time(policy.day_end)
    in_day = _is_time_in_range(local_time, start, end)
    return not in_day
