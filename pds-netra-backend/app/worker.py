"""
Notification worker process entrypoint.
"""

from __future__ import annotations

import logging
import os
import time
import datetime

from .core.db import SessionLocal
from .services.notification_worker import process_outbox_batch
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
    while True:
        try:
            with SessionLocal() as db:
                processed = process_outbox_batch(
                    db,
                    max_attempts=max_attempts,
                    batch_size=batch_size,
                )
                if processed:
                    logger.info("Outbox processed=%s", processed)
                now_utc = datetime.datetime.now(datetime.timezone.utc)
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
