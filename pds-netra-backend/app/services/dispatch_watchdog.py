"""
Dispatch watchdog that creates alerts when movement does not start within 24 hours.
"""

from __future__ import annotations

import datetime
import logging
import os
import threading
import time
from typing import Optional

from sqlalchemy.orm import Session

from ..core.db import SessionLocal
from ..models.dispatch_issue import DispatchIssue
from ..models.event import Event, Alert
from .notifications import notify_alert
from .vehicle_gate import process_vehicle_gate_sessions
from .incident_lifecycle import touch_detection_timestamp


def _ensure_utc(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def _find_first_movement(db: Session, issue: DispatchIssue) -> Optional[Event]:
    deadline = _ensure_utc(issue.issue_time_utc) + datetime.timedelta(hours=24)
    query = db.query(Event).filter(
        Event.godown_id == issue.godown_id,
        Event.event_type == "BAG_MOVEMENT",
        Event.timestamp_utc >= issue.issue_time_utc,
        Event.timestamp_utc <= deadline,
    )
    if issue.camera_id:
        query = query.filter(Event.camera_id == issue.camera_id)
    query = query.order_by(Event.timestamp_utc.asc())
    if not issue.zone_id:
        return query.first()
    for event in query.yield_per(200):
        meta = event.meta or {}
        if meta.get("zone_id") == issue.zone_id:
            return event
    return None


def run_dispatch_watchdog(stop_event: threading.Event) -> None:
    logger = logging.getLogger("DispatchWatchdog")
    # 24h SLA check does not need sub-minute polling by default.
    interval_sec = int(os.getenv("DISPATCH_WATCHDOG_INTERVAL_SEC", "180"))
    interval_sec = max(30, interval_sec)
    logger.info("Dispatch watchdog started (interval=%ss)", interval_sec)
    while not stop_event.is_set():
        try:
            with SessionLocal() as db:
                _process_issues(db, logger)
                if os.getenv("ENABLE_VEHICLE_GATE_WATCHDOG", "true").lower() in {"1", "true", "yes"}:
                    process_vehicle_gate_sessions(db, logger)
        except Exception as exc:
            logger.exception("Dispatch watchdog cycle failed: %s", exc)
        stop_event.wait(interval_sec)
    logger.info("Dispatch watchdog stopped")


def _process_issues(db: Session, logger: logging.Logger) -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    issues = db.query(DispatchIssue).filter(DispatchIssue.status == "OPEN").all()
    for issue in issues:
        issue_time = _ensure_utc(issue.issue_time_utc)
        issue.issue_time_utc = issue_time
        deadline = issue_time + datetime.timedelta(hours=24)
        first_event = _find_first_movement(db, issue)
        if first_event and _ensure_utc(first_event.timestamp_utc) <= deadline:
            issue.status = "STARTED"
            issue.started_at_utc = _ensure_utc(first_event.timestamp_utc)
            db.add(issue)
            continue
        if now < deadline:
            continue
        alert = Alert(
            godown_id=issue.godown_id,
            camera_id=issue.camera_id,
            alert_type="DISPATCH_NOT_STARTED_24H",
            severity_final="warning",
            start_time=now,
            end_time=None,
            status="OPEN",
            summary=(
                "There is a deal in progress, and dispatch has not started within 24 hours of issue."
            ),
            zone_id=issue.zone_id,
            extra=None,
        )
        touch_detection_timestamp(alert, now)
        db.add(alert)
        db.flush()
        issue.status = "ALERTED"
        issue.alerted_at_utc = now
        issue.alert_id = alert.id
        db.add(issue)
        logger.info("Dispatch alert created for issue_id=%s alert_id=%s", issue.id, alert.id)
        try:
            notify_alert(db, alert, None)
        except Exception:
            pass
    db.commit()
