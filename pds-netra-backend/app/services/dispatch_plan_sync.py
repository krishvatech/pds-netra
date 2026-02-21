"""
Dispatch plan sync that auto-creates dispatch issues from a JSON plan file.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ..core.db import SessionLocal
from ..models.dispatch_issue import DispatchIssue


def _parse_ts(value: str | None) -> Optional[datetime.datetime]:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
    except Exception:
        return None


def _issue_exists(
    db: Session,
    godown_id: str,
    camera_id: Optional[str],
    zone_id: Optional[str],
    issue_time_utc: datetime.datetime,
) -> bool:
    query = db.query(DispatchIssue).filter(
        DispatchIssue.godown_id == godown_id,
        DispatchIssue.issue_time_utc == issue_time_utc,
    )
    if camera_id:
        query = query.filter(DispatchIssue.camera_id == camera_id)
    else:
        query = query.filter(DispatchIssue.camera_id.is_(None))
    if zone_id:
        query = query.filter(DispatchIssue.zone_id == zone_id)
    else:
        query = query.filter(DispatchIssue.zone_id.is_(None))
    return db.query(query.exists()).scalar() or False


def _process_plan_file(path: Path, logger: logging.Logger) -> int:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to read dispatch plan file %s: %s", path, exc)
        return 0
    if not isinstance(payload, dict):
        return 0
    godown_id = str(payload.get("godown_id") or "").strip()
    if not godown_id:
        return 0
    plans = payload.get("plans") if isinstance(payload.get("plans"), list) else []
    created = 0
    with SessionLocal() as db:
        for plan in plans:
            if not isinstance(plan, dict):
                continue
            camera_id = str(plan.get("camera_id") or "").strip() or None
            zone_id = str(plan.get("zone_id") or "").strip() or None
            issue_time = _parse_ts(plan.get("start_utc"))
            if not issue_time:
                continue
            if _issue_exists(db, godown_id, camera_id, zone_id, issue_time):
                continue
            issue = DispatchIssue(
                godown_id=godown_id,
                camera_id=camera_id,
                zone_id=zone_id,
                issue_time_utc=issue_time,
                status="OPEN",
            )
            db.add(issue)
            created += 1
        if created:
            db.commit()
    return created


def run_dispatch_plan_sync(stop_event: threading.Event) -> None:
    logger = logging.getLogger("DispatchPlanSync")
    path_env = os.getenv("DISPATCH_PLAN_PATH", "")
    if path_env:
        plan_path = Path(path_env).expanduser()
    else:
        plan_path = Path(__file__).resolve().parents[3] / "pds-netra-edge" / "data" / "dispatch_plan.json"
    interval_sec = int(os.getenv("DISPATCH_PLAN_SYNC_INTERVAL_SEC", "120"))
    interval_sec = max(30, interval_sec)
    logger.info("Dispatch plan sync started (path=%s interval=%ss)", plan_path, interval_sec)
    last_mtime = 0.0
    while not stop_event.is_set():
        if plan_path.exists():
            try:
                mtime = plan_path.stat().st_mtime
            except Exception:
                mtime = 0.0
            if mtime != last_mtime:
                created = _process_plan_file(plan_path, logger)
                if created:
                    logger.info("Dispatch plan sync created %s issues", created)
                last_mtime = mtime
        stop_event.wait(interval_sec)
    logger.info("Dispatch plan sync stopped")
