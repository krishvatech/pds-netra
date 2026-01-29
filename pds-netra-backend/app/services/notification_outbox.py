"""
Notification outbox helpers and alert message templating.
"""

from __future__ import annotations

import datetime
import logging
import os
from dataclasses import dataclass
from typing import Optional, Iterable

from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from ..models.event import Alert, Event, AlertEventLink
from ..models.godown import Godown, Camera
from ..models.notification_endpoint import NotificationEndpoint
from ..models.notification_outbox import NotificationOutbox
from ..models.notification_recipient import NotificationRecipient


logger = logging.getLogger("notification_outbox")


@dataclass
class NotificationContent:
    title: str
    summary: str
    whatsapp_text: str
    email_subject: str
    email_body: str
    media_url: Optional[str] = None


def _to_ist(ts: datetime.datetime) -> datetime.datetime:
    tz = ZoneInfo("Asia/Kolkata")
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    return ts.astimezone(tz)


def _human_alert_type(alert_type: str) -> str:
    mapping = {
        "FIRE_DETECTED": "Fire Detected",
        "ANIMAL_INTRUSION": "Animal Intrusion",
        "AFTER_HOURS_PERSON_PRESENCE": "After-hours Person Detected",
        "AFTER_HOURS_VEHICLE_PRESENCE": "After-hours Vehicle Detected",
        "BLACKLIST_PERSON_MATCH": "Blacklisted Person Detected",
        "DISPATCH_NOT_STARTED_24H": "Dispatch Not Started (24h)",
        "DISPATCH_MOVEMENT_DELAY": "Dispatch Movement Delay",
        "CAMERA_HEALTH_ISSUE": "Camera Health Issue",
        "SECURITY_UNAUTH_ACCESS": "Unauthorized Access",
    }
    return mapping.get(alert_type, alert_type.replace("_", " ").title())


def _evidence_url(alert: Alert, event: Optional[Event]) -> Optional[str]:
    extra = alert.extra if isinstance(alert.extra, dict) else {}
    for key in ("snapshot_url", "clip_url", "image_url"):
        val = extra.get(key)
        if val:
            return str(val)
    if event is not None:
        if event.image_url:
            return event.image_url
        if event.clip_url:
            return event.clip_url
        meta = event.meta or {}
        extra = meta.get("extra") if isinstance(meta, dict) else None
        if isinstance(extra, dict):
            snap = extra.get("snapshot_url")
            if snap:
                return str(snap)
    return None


def _build_details(alert: Alert) -> str:
    extra = alert.extra if isinstance(alert.extra, dict) else {}
    if alert.alert_type == "FIRE_DETECTED":
        classes = extra.get("fire_classes") or []
        conf = extra.get("fire_confidence")
        class_text = ", ".join(classes) if classes else "fire/smoke"
        if conf is not None:
            return f"{class_text} | Confidence {float(conf):.2f}"
        return class_text
    if alert.alert_type == "ANIMAL_INTRUSION":
        species = extra.get("animal_species") or "animal"
        count = extra.get("animal_count")
        if count:
            return f"{species} | Count {count}"
        return str(species)
    if alert.alert_type in {"AFTER_HOURS_PERSON_PRESENCE", "AFTER_HOURS_VEHICLE_PRESENCE"}:
        count = extra.get("detected_count")
        plate = extra.get("vehicle_plate")
        bits = []
        if count:
            bits.append(f"Count {count}")
        if plate:
            bits.append(f"Plate {plate}")
        return " | ".join(bits) if bits else "Presence detected"
    if alert.alert_type == "BLACKLIST_PERSON_MATCH":
        person = extra.get("person_name") or "Unknown person"
        score = extra.get("match_score")
        if score is not None:
            return f"{person} | Match {float(score):.3f}"
        return str(person)
    if alert.alert_type == "DISPATCH_MOVEMENT_DELAY":
        plate = extra.get("plate_norm") or extra.get("plate_raw")
        age = extra.get("age_hours")
        threshold = extra.get("threshold_hours")
        bits = []
        if plate:
            bits.append(f"Vehicle {plate}")
        if age is not None:
            bits.append(f"Age {float(age):.1f}h")
        if threshold is not None:
            bits.append(f"Threshold {threshold}h")
        return " | ".join(bits) if bits else "Dispatch delay"
    return alert.summary or _human_alert_type(alert.alert_type)


def _dashboard_link(alert: Alert) -> Optional[str]:
    base = os.getenv("DASHBOARD_BASE_URL", "").rstrip("/")
    if not base:
        return None
    return f"{base}/dashboard/alerts/{alert.id}"


def build_alert_notification(db: Session, alert: Alert, event: Optional[Event] = None) -> NotificationContent:
    godown = db.get(Godown, alert.godown_id)
    camera = db.get(Camera, alert.camera_id) if alert.camera_id else None
    godown_name = godown.name if godown and godown.name else alert.godown_id
    camera_name = camera.label if camera and camera.label else (alert.camera_id or "Unknown camera")
    timestamp = _to_ist(alert.start_time)
    ts_str = timestamp.strftime("%d %b %Y %H:%M IST")
    alert_title = _human_alert_type(alert.alert_type)
    details = _build_details(alert)
    evidence = _evidence_url(alert, event)
    link = _dashboard_link(alert)

    line1 = f"{alert_title} | {godown_name}"
    line2 = f"Camera: {camera_name} | {ts_str}"
    line3 = f"Details: {details}"
    lines = [line1, line2, line3]
    if evidence:
        lines.append(f"Evidence: {evidence}")
    if link:
        lines.append(f"Dashboard: {link}")
    whatsapp_text = "\n".join(lines[:4]) if len(lines) > 4 else "\n".join(lines)

    email_subject = f"PDS Netra: {alert_title}"
    email_body = (
        f"<h3>{alert_title}</h3>"
        f"<p><strong>Godown:</strong> {godown_name}</p>"
        f"<p><strong>Camera:</strong> {camera_name}</p>"
        f"<p><strong>Time:</strong> {ts_str}</p>"
        f"<p><strong>Details:</strong> {details}</p>"
    )
    if evidence:
        email_body += f"<p><strong>Evidence:</strong> <a href=\"{evidence}\">{evidence}</a></p>"
    if link:
        email_body += f"<p><strong>Dashboard:</strong> <a href=\"{link}\">{link}</a></p>"

    return NotificationContent(
        title=alert_title,
        summary=details,
        whatsapp_text=whatsapp_text,
        email_subject=email_subject,
        email_body=email_body,
        media_url=evidence,
    )


def _targets_from_endpoints(
    endpoints: Iterable[NotificationEndpoint],
    *,
    godown_id: Optional[str],
    scope: str,
) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    for ep in endpoints:
        if not ep.is_enabled:
            continue
        ep_scope = (ep.scope or "").upper()
        if ep_scope == "GODOWN":
            ep_scope = "GODOWN_MANAGER"
        if ep_scope == scope:
            if scope == "GODOWN_MANAGER":
                if godown_id and ep.godown_id == godown_id:
                    targets.append((ep.channel, ep.target))
            else:
                targets.append((ep.channel, ep.target))
    return targets


def _targets_from_recipients(
    recipients: Iterable[NotificationRecipient],
    *,
    godown_id: Optional[str],
    scope: str,
) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    for row in recipients:
        role = (row.role or "").upper()
        if role == "GODOWN":
            role = "GODOWN_MANAGER"
        if role == scope:
            if scope == "GODOWN_MANAGER":
                if godown_id and row.godown_id == godown_id:
                    targets.append((row.channel, row.destination))
            else:
                targets.append((row.channel, row.destination))
    return targets


def _recipient_targets_from_env(*, godown_id: Optional[str], scope: str) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    if scope == "HQ":
        hq_emails = [e.strip() for e in os.getenv("WATCHLIST_NOTIFY_HQ_EMAILS", "").split(",") if e.strip()]
        hq_whatsapp = [e.strip() for e in os.getenv("WATCHLIST_NOTIFY_HQ_WHATSAPP", "").split(",") if e.strip()]
        for email in hq_emails:
            targets.append(("EMAIL", email))
        for phone in hq_whatsapp:
            targets.append(("WHATSAPP", phone))
    if scope == "GODOWN_MANAGER" and godown_id:
        mapping = os.getenv("WATCHLIST_NOTIFY_GODOWN_EMAILS", "")
        targets += _parse_mapping(mapping, godown_id, channel="EMAIL")
        mapping = os.getenv("WATCHLIST_NOTIFY_GODOWN_WHATSAPP", "")
        targets += _parse_mapping(mapping, godown_id, channel="WHATSAPP")
    return targets


def _parse_mapping(raw: str, godown_id: str, channel: str) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    if not raw:
        return targets
    for entry in raw.split(","):
        if ":" not in entry:
            continue
        gdn, dest = entry.split(":", 1)
        if gdn.strip() == godown_id and dest.strip():
            targets.append((channel, dest.strip()))
    return targets


def resolve_notification_targets(
    db: Session,
    *,
    godown_id: Optional[str],
    scope: str,
) -> list[tuple[str, str]]:
    endpoints = db.query(NotificationEndpoint).all()
    if endpoints:
        targets = _targets_from_endpoints(endpoints, godown_id=godown_id, scope=scope)
        if targets:
            return targets
    recipients = db.query(NotificationRecipient).all()
    if recipients:
        targets = _targets_from_recipients(recipients, godown_id=godown_id, scope=scope)
        if targets:
            return targets
    return _recipient_targets_from_env(godown_id=godown_id, scope=scope)


def _find_event_for_alert(db: Session, alert: Alert, event: Optional[Event]) -> Optional[Event]:
    if event is not None:
        return event
    link = (
        db.query(AlertEventLink)
        .filter(AlertEventLink.alert_id == alert.id)
        .order_by(AlertEventLink.event_id.asc())
        .first()
    )
    return link.event if link else None


def enqueue_alert_notifications(db: Session, alert: Alert, *, event: Optional[Event] = None) -> int:
    if not alert.public_id:
        db.flush()
    targets = resolve_notification_targets(db, godown_id=alert.godown_id, scope="GODOWN_MANAGER")
    if not targets:
        logger.info("No notification targets configured for godown=%s", alert.godown_id)
        return 0
    event = _find_event_for_alert(db, alert, event)
    content = build_alert_notification(db, alert, event)
    created = 0
    for channel, target in targets:
        channel_norm = channel.upper()
        if channel_norm not in {"WHATSAPP", "EMAIL"}:
            continue
        exists = (
            db.query(NotificationOutbox)
            .filter(
                NotificationOutbox.alert_id == alert.public_id,
                NotificationOutbox.channel == channel_norm,
                NotificationOutbox.target == target,
            )
            .first()
        )
        if exists:
            continue
        subject = content.email_subject if channel_norm == "EMAIL" else None
        message = content.email_body if channel_norm == "EMAIL" else content.whatsapp_text
        outbox = NotificationOutbox(
            kind="ALERT",
            alert_id=alert.public_id,
            report_id=None,
            channel=channel_norm,
            target=target,
            subject=subject,
            message=message,
            media_url=content.media_url,
            status="PENDING",
            attempts=0,
            next_retry_at=None,
            last_error=None,
            provider_message_id=None,
        )
        db.add(outbox)
        created += 1
    if created:
        db.commit()
    return created


def enqueue_report_notifications(
    db: Session,
    *,
    report_id: str,
    message_text: str,
    email_html: str,
    subject: str,
) -> int:
    targets = resolve_notification_targets(db, godown_id=None, scope="HQ")
    if not targets:
        logger.info("No HQ notification targets configured")
        return 0
    created = 0
    for channel, target in targets:
        channel_norm = channel.upper()
        if channel_norm not in {"WHATSAPP", "EMAIL"}:
            continue
        exists = (
            db.query(NotificationOutbox)
            .filter(
                NotificationOutbox.report_id == report_id,
                NotificationOutbox.channel == channel_norm,
                NotificationOutbox.target == target,
            )
            .first()
        )
        if exists:
            continue
        message = email_html if channel_norm == "EMAIL" else message_text
        outbox = NotificationOutbox(
            kind="REPORT",
            alert_id=None,
            report_id=report_id,
            channel=channel_norm,
            target=target,
            subject=subject if channel_norm == "EMAIL" else None,
            message=message,
            media_url=None,
            status="PENDING",
            attempts=0,
            next_retry_at=None,
            last_error=None,
            provider_message_id=None,
        )
        db.add(outbox)
        created += 1
    if created:
        db.commit()
    return created
