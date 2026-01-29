from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.after_hours import AfterHoursPolicy, is_after_hours


def test_after_hours_boundaries():
    policy = AfterHoursPolicy(
        day_start="09:00",
        day_end="19:00",
        presence_allowed=False,
        cooldown_seconds=120,
        enabled=True,
        timezone="Asia/Kolkata",
    )
    tz = ZoneInfo("Asia/Kolkata")

    assert is_after_hours(datetime(2026, 1, 1, 18, 59, tzinfo=tz), policy) is False
    assert is_after_hours(datetime(2026, 1, 1, 19, 0, tzinfo=tz), policy) is True
    assert is_after_hours(datetime(2026, 1, 2, 2, 0, tzinfo=tz), policy) is True
    assert is_after_hours(datetime(2026, 1, 2, 9, 0, tzinfo=tz), policy) is False
