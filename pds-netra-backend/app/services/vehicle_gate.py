"""
Vehicle gate session tracking and reminder alerts based on ANPR hits.
"""

from __future__ import annotations

import datetime
import logging
import os
from typing import Optional

from sqlalchemy.orm import Session

from ..models.event import Alert
from ..models.vehicle_gate_session import VehicleGateSession
from .notifications import notify_dispatch_movement_delay


def _normalize_plate(text: str) -> str:
    return "".join(ch for ch in text.upper() if ch.isalnum())


def _thresholds() -> list[int]:
    raw = os.getenv("DISPATCH_MOVEMENT_THRESHOLDS_HOURS", "3,6,9,12,24")
    out: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            val = int(float(part))
        except Exception:
            continue
        if val > 0:
            out.append(val)
    return sorted(set(out)) or [3, 6, 9, 12, 24]


def _ensure_utc(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def _coerce_direction(direction: Optional[str]) -> str:
    if not direction:
        return "UNKNOWN"
    direction = direction.strip().upper()
    if direction not in {"ENTRY", "EXIT", "UNKNOWN"}:
        return "UNKNOWN"
    return direction


def _should_fallback_exit(open_session: VehicleGateSession, now: datetime.datetime) -> bool:
    enabled = os.getenv("DISPATCH_MOVEMENT_FALLBACK_EXIT", "true").lower() in {"1", "true", "yes"}
    if not enabled:
        return False
    try:
        min_gap_min = int(os.getenv("DISPATCH_MOVEMENT_FALLBACK_EXIT_GAP_MIN", "10"))
    except Exception:
        min_gap_min = 10
    gap = max(1, min_gap_min)
    last_seen = _ensure_utc(open_session.last_seen_at)
    return (now - last_seen).total_seconds() >= gap * 60


def _find_open_session(db: Session, godown_id: str, plate_norm: str) -> Optional[VehicleGateSession]:
    return (
        db.query(VehicleGateSession)
        .filter(
            VehicleGateSession.godown_id == godown_id,
            VehicleGateSession.plate_norm == plate_norm,
            VehicleGateSession.status == "OPEN",
        )
        .order_by(VehicleGateSession.entry_at.desc())
        .first()
    )


def _close_alerts_for_session(db: Session, session: VehicleGateSession, closed_at: datetime.datetime) -> None:
    alerts = (
        db.query(Alert)
        .filter(
            Alert.godown_id == session.godown_id,
            Alert.alert_type == "DISPATCH_MOVEMENT_DELAY",
            Alert.status == "OPEN",
        )
        .all()
    )
    for alert in alerts:
        extra = alert.extra or {}
        if not isinstance(extra, dict):
            continue
        if extra.get("plate_norm") != session.plate_norm:
            continue
        alert.status = "CLOSED"
        alert.end_time = closed_at
        db.add(alert)


def handle_anpr_hit_event(db: Session, *, godown_id: str, camera_id: str, event_id: str, occurred_at: datetime.datetime, meta: dict, image_url: Optional[str]) -> Optional[VehicleGateSession]:
    logger = logging.getLogger("VehicleGateSessions")
    plate_raw = (meta.get("plate_raw") or meta.get("plate_text") or "").strip()
    if not plate_raw:
        return None
    plate_norm = (meta.get("plate_norm") or _normalize_plate(plate_raw)).strip()
    if not plate_norm:
        return None
    direction = _coerce_direction(meta.get("direction"))
    occurred_at = _ensure_utc(occurred_at)

    open_session = _find_open_session(db, godown_id, plate_norm)

    if direction == "UNKNOWN":
        if open_session and _should_fallback_exit(open_session, occurred_at):
            direction = "EXIT"
            logger.info(
                "ANPR fallback direction EXIT plate=%s godown=%s camera=%s",
                plate_norm,
                godown_id,
                camera_id,
            )
        elif open_session is None:
            direction = "ENTRY"
            logger.info(
                "ANPR fallback direction ENTRY plate=%s godown=%s camera=%s",
                plate_norm,
                godown_id,
                camera_id,
            )

    if direction == "ENTRY":
        if open_session:
            if open_session.entry_event_id == event_id:
                return open_session
            open_session.anpr_camera_id = camera_id
            open_session.last_seen_at = occurred_at
            open_session.plate_raw = plate_raw
            open_session.last_snapshot_url = image_url or open_session.last_snapshot_url
            db.add(open_session)
            return open_session
        session = VehicleGateSession(
            godown_id=godown_id,
            anpr_camera_id=camera_id,
            plate_raw=plate_raw,
            plate_norm=plate_norm,
            entry_at=occurred_at,
            exit_at=None,
            status="OPEN",
            last_seen_at=occurred_at,
            entry_event_id=event_id,
            exit_event_id=None,
            reminders_sent={},
            last_snapshot_url=image_url,
        )
        db.add(session)
        return session

    if direction == "EXIT":
        if open_session:
            if open_session.exit_event_id == event_id:
                return open_session
            open_session.anpr_camera_id = camera_id
            open_session.exit_at = occurred_at
            open_session.status = "CLOSED"
            open_session.last_seen_at = occurred_at
            open_session.exit_event_id = event_id
            open_session.last_snapshot_url = image_url or open_session.last_snapshot_url
            db.add(open_session)
            _close_alerts_for_session(db, open_session, occurred_at)
            return open_session
        session = VehicleGateSession(
            godown_id=godown_id,
            anpr_camera_id=camera_id,
            plate_raw=plate_raw,
            plate_norm=plate_norm,
            entry_at=occurred_at,
            exit_at=occurred_at,
            status="CLOSED",
            last_seen_at=occurred_at,
            entry_event_id=None,
            exit_event_id=event_id,
            reminders_sent={"exit_without_entry": occurred_at.isoformat()},
            last_snapshot_url=image_url,
        )
        db.add(session)
        return session

    return None


def _session_age_hours(session: VehicleGateSession, now_utc: datetime.datetime) -> float:
    start = _ensure_utc(session.entry_at)
    delta = now_utc - start
    return max(0.0, delta.total_seconds() / 3600.0)


def _find_open_alert(db: Session, *, godown_id: str, plate_norm: str, threshold: int) -> Optional[Alert]:
    alerts = (
        db.query(Alert)
        .filter(
            Alert.godown_id == godown_id,
            Alert.alert_type == "DISPATCH_MOVEMENT_DELAY",
            Alert.status == "OPEN",
        )
        .order_by(Alert.start_time.desc())
        .all()
    )
    for alert in alerts:
        extra = alert.extra or {}
        if not isinstance(extra, dict):
            continue
        if extra.get("plate_norm") != plate_norm:
            continue
        if int(extra.get("threshold_hours") or 0) != int(threshold):
            continue
        return alert
    return None


def process_vehicle_gate_sessions(db: Session, logger: Optional[logging.Logger] = None) -> None:
    logger = logger or logging.getLogger("VehicleGateSessions")
    now = datetime.datetime.now(datetime.timezone.utc)
    thresholds = _thresholds()
    sessions = db.query(VehicleGateSession).filter(VehicleGateSession.status == "OPEN").all()
    for session in sessions:
        reminders = session.reminders_sent or {}
        if not isinstance(reminders, dict):
            reminders = {}
        age_hours = _session_age_hours(session, now)
        for threshold in thresholds:
            key = str(threshold)
            if age_hours < threshold:
                break
            if key in reminders:
                continue
            existing = _find_open_alert(db, godown_id=session.godown_id, plate_norm=session.plate_norm, threshold=threshold)
            if existing:
                extra = dict(existing.extra or {})
                extra["last_seen_at"] = session.last_seen_at.isoformat()
                extra["age_hours"] = round(age_hours, 2)
                if session.last_snapshot_url:
                    extra["snapshot_url"] = session.last_snapshot_url
                existing.extra = extra
                db.add(existing)
                reminders[key] = now.isoformat()
                session.reminders_sent = reminders
                db.add(session)
                continue
            severity = "critical" if threshold >= 24 else "warning"
            alert = Alert(
                godown_id=session.godown_id,
                camera_id=session.anpr_camera_id,
                alert_type="DISPATCH_MOVEMENT_DELAY",
                severity_final=severity,
                start_time=now,
                end_time=None,
                status="OPEN",
                summary=f"Vehicle entered but not exited after {threshold} hours",
                zone_id=None,
                extra={
                    "plate_raw": session.plate_raw,
                    "plate_norm": session.plate_norm,
                    "entry_at": session.entry_at.isoformat(),
                    "age_hours": round(age_hours, 2),
                    "threshold_hours": threshold,
                    "last_seen_at": session.last_seen_at.isoformat(),
                    "snapshot_url": session.last_snapshot_url,
                },
            )
            db.add(alert)
            db.flush()
            reminders[key] = now.isoformat()
            session.reminders_sent = reminders
            db.add(session)
            logger.info(
                "Dispatch movement delay alert created plate=%s threshold=%s godown=%s",
                session.plate_norm,
                threshold,
                session.godown_id,
            )
            try:
                notify_dispatch_movement_delay(
                    db,
                    alert,
                    plate=session.plate_norm,
                    threshold_hours=threshold,
                    age_hours=age_hours,
                    snapshot_url=session.last_snapshot_url,
                )
            except Exception:
                pass
    db.commit()


def compute_next_threshold(reminders_sent: dict | None) -> Optional[int]:
    thresholds = _thresholds()
    reminders_sent = reminders_sent or {}
    if not isinstance(reminders_sent, dict):
        return thresholds[0] if thresholds else None
    for threshold in thresholds:
        if str(threshold) not in reminders_sent:
            return threshold
    return None
