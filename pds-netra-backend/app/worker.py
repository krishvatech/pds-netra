"""
Notification worker process entrypoint.
"""

from __future__ import annotations

import datetime
import logging
import os
import time
from pathlib import Path

from sqlalchemy.orm import Session

def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        raise RuntimeError(f".env not found at: {env_path}")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value

# Force-load .env from pds-netra-backend/.env no matter where module is imported from
backend_root = Path(__file__).resolve().parents[1]  # .../pds-netra-backend
env_path = backend_root / ".env"
_load_env_file(env_path)

QUIET_DEFAULT = datetime.timedelta(seconds=60)
QUIET_FIRE = datetime.timedelta(seconds=120)
FIRE_ALERT_TYPES = {"FIRE_DETECTED"}


def close_stale_incidents(db: Session, *, now: datetime.datetime | None = None) -> int:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    closed = 0
    rows = (
        db.query(Alert)
        .filter(Alert.status.in_(["OPEN", "ACK"]))
        .all()
    )
    for alert in rows:
        last_seen = alert.last_detection_at or alert.start_time
        if last_seen is None:
            continue
        quiet = QUIET_FIRE if alert.alert_type in FIRE_ALERT_TYPES else QUIET_DEFAULT
        if (now - last_seen) >= quiet:
            mark_alert_closed(alert, now)
            db.add(alert)
            closed += 1
    if closed:
        db.commit()
    return closed

from .core.config import settings  # ensures .env is loaded for standalone worker
from .core.db import SessionLocal
from .models.event import Alert
from .services.incident_lifecycle import mark_alert_closed
from .services.notification_worker import _build_providers, process_outbox_batch
from .services.alert_reports import generate_hq_report, IST


def main() -> int:
    interval = float(os.getenv("NOTIFY_WORKER_INTERVAL_SEC", "10"))
    batch_size = int(os.getenv("NOTIFY_WORKER_BATCH_SIZE", "50"))
    max_attempts = int(os.getenv("NOTIFY_MAX_ATTEMPTS", "6"))
    daily_enabled = os.getenv("HQ_REPORT_DAILY_ENABLED", "true").lower() in {"1", "true", "yes"}
    daily_time = os.getenv("HQ_REPORT_DAILY_TIME", "09:00")
    hourly_enabled = os.getenv("HQ_REPORT_HOURLY_ENABLED", "false").lower() in {"1", "true", "yes"}
    hourly_minute = int(os.getenv("HQ_REPORT_HOURLY_MINUTE", "5"))
    last_daily_date = None
    last_hourly_key = None
    logger = logging.getLogger("notification_worker")
    logging.basicConfig(level=logging.INFO)
    logger.info(
        "Notification worker started interval=%ss batch=%s max_attempts=%s",
        interval,
        batch_size,
        max_attempts,
    )
    _load_env_file(env_path)
    _ = settings  # load environment before the loop
    providers = _build_providers()
    while True:
        try:
            with SessionLocal() as db:
                processed = process_outbox_batch(
                    db,
                    providers=providers,
                    max_attempts=max_attempts,
                    batch_size=batch_size,
                )
                if processed:
                    logger.info("Outbox processed=%s", processed)
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                closed = close_stale_incidents(db, now=now_utc)
                if closed:
                    logger.info("Incidents auto-closed=%s", closed)
                now_ist = now_utc.astimezone(IST)
                if daily_enabled:
                    try:
                        hh, mm = [int(x) for x in daily_time.split(":", 1)]
                        scheduled = now_ist.replace(hour=hh, minute=mm, second=0, microsecond=0)
                    except Exception:
                        scheduled = now_ist.replace(hour=9, minute=0, second=0, microsecond=0)
                    if now_ist >= scheduled and last_daily_date != now_ist.date():
                        generate_hq_report(db, period="24h", now_utc=now_utc)
                        last_daily_date = now_ist.date()
                        logger.info("HQ daily report generated for %s", last_daily_date)
                if hourly_enabled:
                    hourly_key = (now_ist.date(), now_ist.hour)
                    if now_ist.minute >= hourly_minute and last_hourly_key != hourly_key:
                        generate_hq_report(db, period="1h", now_utc=now_utc)
                        last_hourly_key = hourly_key
                        logger.info("HQ hourly report generated for %s:%s", now_ist.date(), now_ist.hour)
        except Exception as exc:
            logger.exception("Worker loop failed: %s", exc)
        time.sleep(max(1.0, interval))


if __name__ == "__main__":
    raise SystemExit(main())
