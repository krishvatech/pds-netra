"""
Notification worker process entrypoint.
"""

from __future__ import annotations

import datetime
import logging
import os
import time
from pathlib import Path

from sqlalchemy import and_, or_
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


# Force-load .env from backend root
backend_root = Path(__file__).resolve().parents[1]
env_path = backend_root / ".env"
_load_env_file(env_path)

ALERT_AUTO_CLOSE_DEFAULT_SEC = int(os.getenv("ALERT_AUTO_CLOSE_DEFAULT_SEC", "60"))
ALERT_AUTO_CLOSE_FIRE_SEC = int(os.getenv("ALERT_AUTO_CLOSE_FIRE_SEC", "120"))
FIRE_ALERT_TYPES = {"FIRE_DETECTED"}


from .core.config import settings  # noqa: E402
from .core.db import SessionLocal  # noqa: E402
from .models.event import Alert  # noqa: E402
from .services.incident_lifecycle import mark_alert_closed  # noqa: E402
from .services.notification_worker import _build_providers, process_outbox_batch  # noqa: E402
from .services.alert_reports import generate_hq_report, IST  # noqa: E402

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker")


def close_stale_incidents(db: Session, *, now: datetime.datetime | None = None) -> int:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    closed = 0

    candidates: dict[str, Alert] = {}

    def _due_filter(cutoff: datetime.datetime):
        return or_(
            and_(
                Alert.last_detection_at.isnot(None),
                Alert.last_detection_at <= cutoff,
            ),
            and_(
                Alert.last_detection_at.is_(None),
                Alert.start_time <= cutoff,
            ),
        )

    if ALERT_AUTO_CLOSE_DEFAULT_SEC > 0:
        default_cutoff = now - datetime.timedelta(seconds=ALERT_AUTO_CLOSE_DEFAULT_SEC)
        default_rows = (
            db.query(Alert)
            .filter(
                Alert.status.in_(["OPEN", "ACK"]),
                ~Alert.alert_type.in_(tuple(FIRE_ALERT_TYPES)),
                _due_filter(default_cutoff),
            )
            .all()
        )
        for alert in default_rows:
            candidates[str(alert.id)] = alert

    if ALERT_AUTO_CLOSE_FIRE_SEC > 0:
        fire_cutoff = now - datetime.timedelta(seconds=ALERT_AUTO_CLOSE_FIRE_SEC)
        fire_rows = (
            db.query(Alert)
            .filter(
                Alert.status.in_(["OPEN", "ACK"]),
                Alert.alert_type.in_(tuple(FIRE_ALERT_TYPES)),
                _due_filter(fire_cutoff),
            )
            .all()
        )
        for alert in fire_rows:
            candidates[str(alert.id)] = alert

    for alert in candidates.values():
        last_seen = alert.last_detection_at or alert.start_time
        if not last_seen:
            continue
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=datetime.timezone.utc)

        quiet_sec = ALERT_AUTO_CLOSE_FIRE_SEC if alert.alert_type in FIRE_ALERT_TYPES else ALERT_AUTO_CLOSE_DEFAULT_SEC
        if quiet_sec <= 0:
            continue  # auto-close disabled

        if (now - last_seen).total_seconds() >= quiet_sec:
            mark_alert_closed(alert, now)
            db.add(alert)
            closed += 1

    if closed:
        db.commit()
    return closed


def main() -> int:
    logger.info("✅ Worker booted (pid=%s)", os.getpid())
    interval = int(os.getenv("WORKER_INTERVAL_SEC", "10"))
    report_interval = int(os.getenv("HQ_REPORT_INTERVAL_SEC", "3600"))
    last_report_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=report_interval)

    providers = _build_providers()
    logger.info("Worker started interval=%ss", interval)

    while True:
        try:
            with SessionLocal() as db:
                process_outbox_batch(db, providers=providers)
                close_stale_incidents(db)

                now = datetime.datetime.now(datetime.timezone.utc)
                if (now - last_report_at).total_seconds() >= report_interval:
                    try:
                        generate_hq_report(db, now_utc=now)
                        last_report_at = now
                    except Exception:
                        logger.exception("Failed to generate HQ report")

            time.sleep(interval)
        except KeyboardInterrupt:
            return 0
        except Exception:
            logger.exception("Worker loop error")
            time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
