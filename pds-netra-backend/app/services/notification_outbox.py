"""
Notification outbox helpers and alert message templating.
"""

from __future__ import annotations

import datetime
import logging
import os
from dataclasses import dataclass
import html
import json
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from .ack_tokens import issue_ack_token

from ..models.event import Alert, Event, AlertEventLink
from ..models.godown import Godown, Camera
from ..models.notification_endpoint import NotificationEndpoint
from ..models.notification_outbox import NotificationOutbox
from ..models.notification_recipient import NotificationRecipient


logger = logging.getLogger("notification_outbox")

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
ALERT_ACK_TTL_MIN = int(os.getenv("ALERT_ACK_TTL_MIN", str(7 * 24 * 60)))  # default: 7 days


@dataclass
class NotificationContent:
    title: str
    summary: str
    whatsapp_text: str
    email_subject: str
    email_body: str
    call_script: str
    media_url: Optional[str] = None


IST = ZoneInfo("Asia/Kolkata")


def _format_ts(ts: datetime.datetime | None) -> str:
    if not ts:
        return "-"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    return ts.astimezone(IST).strftime("%d %b %Y %H:%M IST")


def _safe(v: Any) -> str:
    return html.escape(str(v)) if v is not None else ""


def _find_event_for_alert(db: Session, alert: Alert, event: Optional[Event]) -> Optional[Event]:
    if event:
        return event
    link = (
        db.query(AlertEventLink)
        .filter(AlertEventLink.alert_id == alert.id)
        .order_by(AlertEventLink.event_id.desc())
        .first()
    )
    if not link:
        return None
    return db.get(Event, link.event_id)


def _build_evidence_url(event: Optional[Event]) -> Optional[str]:
    if not event:
        return None
    if event.image_url:
        return event.image_url
    return None


def build_alert_notification(db: Session, alert: Alert, event: Optional[Event] = None) -> NotificationContent:
    godown = db.get(Godown, alert.godown_id)
    camera = None
    if alert.camera_id:
       camera = (
        db.query(Camera)
        .filter(Camera.id == alert.camera_id, Camera.godown_id == alert.godown_id)
        .first()
        )


    evidence = _build_evidence_url(event)

    if camera:
      cam_label = (
        getattr(camera, "name", None)
        or getattr(camera, "label", None)
        or getattr(camera, "location", None)
        or getattr(camera, "camera_name", None)
        or getattr(camera, "id", None)
        or (alert.camera_id or "-")
      )
    else:
       cam_label = alert.camera_id or "-"

    godown_label = godown.name if godown else alert.godown_id

    alert_title = alert.title or f"{alert.alert_type}"
    details = alert.summary or ""

    whatsapp_text = (
        f"{alert_title}\n"
        f"Godown: {godown_label}\n"
        f"Camera: {cam_label}\n"
        f"Time: {_format_ts(alert.start_time)}\n"
        f"Details: {details}"
    )
    if evidence:
        whatsapp_text += f"\nEvidence: {evidence}"

    email_subject = alert_title
    email_body = (
        f"<h3>{_safe(alert_title)}</h3>"
        f"<p><strong>Godown:</strong> {_safe(godown_label)}<br/>"
        f"<strong>Camera:</strong> {_safe(cam_label)}<br/>"
        f"<strong>Time:</strong> {_safe(_format_ts(alert.start_time))}</p>"
        f"<p><strong>Details:</strong> {_safe(details)}</p>"
    )
    if evidence:
        email_body += f"<p><strong>Evidence:</strong> <a href=\"{evidence}\">{evidence}</a></p>"

    call_script = (
        f"Alert: {alert_title}. Godown {godown_label}. Camera {cam_label}. "
        f"Time {_format_ts(alert.start_time)}."
    )

    # optional dashboard link (already existed)
    link = None
    if alert.public_id:
        link = f"{PUBLIC_BASE_URL}/dashboard/alerts/{alert.public_id}"
    if link:
        email_body += f"<p><strong>Dashboard:</strong> <a href=\"{link}\">{link}</a></p>"

    return NotificationContent(
        title=alert_title,
        summary=details,
        whatsapp_text=whatsapp_text,
        email_subject=email_subject,
        email_body=email_body,
        call_script=call_script,
        media_url=evidence,
    )


def _normalize_target(channel: str | None, target: str | None) -> tuple[str, str] | None:
    if not channel or not target:
        return None
    channel_norm = channel.strip().upper()
    target_norm = target.strip()
    if not channel_norm or not target_norm:
        return None
    return channel_norm, target_norm


def _merge_targets(*sources: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    merged: list[tuple[str, str]] = []
    for source in sources:
        for channel, target in source:
            key = (channel, target)
            if key in seen:
                continue
            seen.add(key)
            merged.append((channel, target))
    return merged


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
        if ep.scope != scope:
            continue
        if ep.godown_id and godown_id and ep.godown_id != godown_id:
            continue
        norm = _normalize_target(ep.channel, ep.target)
        if norm:
            targets.append(norm)
    return targets


def _targets_from_recipients(
    recipients: Iterable[NotificationRecipient],
) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    for r in recipients:
        if not r.is_enabled:
            continue
        norm = _normalize_target(r.channel, r.target)
        if norm:
            targets.append(norm)
    return targets


def resolve_notification_targets(
    db: Session,
    *,
    godown_id: Optional[str],
    scopes: Iterable[str],
) -> list[tuple[str, str]]:
    endpoints = db.query(NotificationEndpoint).all()
    recipients = db.query(NotificationRecipient).all()
    targets: list[tuple[str, str]] = []
    for scope in scopes:
        targets.extend(_targets_from_endpoints(endpoints, godown_id=godown_id, scope=scope))
    targets = _merge_targets(targets, _targets_from_recipients(recipients))
    return targets


def _cooldown_ok(alert: Alert, channel: str, now: datetime.datetime) -> bool:
    cooldown_s = int(os.getenv("ALERT_NOTIFY_COOLDOWN_SEC", "30"))
    if cooldown_s <= 0:
        return True
    last = None
    if channel == "WHATSAPP":
        last = alert.last_whatsapp_at
    elif channel == "EMAIL":
        last = alert.last_email_at
    elif channel == "CALL":
        last = alert.last_call_at
    if not last:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=datetime.timezone.utc)
    return (now - last).total_seconds() >= cooldown_s


def enqueue_alert_notifications(db: Session, alert: Alert, *, event: Optional[Event] = None) -> int:
    if not alert.public_id:
        db.flush()

    targets = resolve_notification_targets(
        db,
        godown_id=alert.godown_id,
        scopes=("GODOWN_MANAGER", "HQ"),
    )
    if not targets:
        logger.info("No notification targets configured for godown=%s", alert.godown_id)
        return 0

    # --- Option A: Human ACK via link from WhatsApp/Email ---
    # We always issue a fresh one-time token when queuing notifications so the outgoing
    # message contains a valid raw token (we only store its hash on the Alert).
    ack_url: str | None = None
    if alert.status != "ACK" and alert.acknowledged_at is None:
        raw, token_hash, expires_at = issue_ack_token(ttl_minutes=ALERT_ACK_TTL_MIN)
        alert.ack_token_hash = token_hash
        alert.ack_token_expires_at = expires_at
        alert.ack_token_used_at = None
        ack_url = f"{PUBLIC_BASE_URL}/api/v1/alerts/{alert.public_id}/ack-link?token={raw}"

    event = _find_event_for_alert(db, alert, event)
    content = build_alert_notification(db, alert, event)

    if ack_url:
        content.whatsapp_text = f"{content.whatsapp_text}\n\nAcknowledge: {ack_url}"
        content.email_body += f"<p><strong>Acknowledge:</strong> <a href=\"{ack_url}\">{ack_url}</a></p>"

    created = 0
    now = datetime.datetime.now(datetime.timezone.utc)
    for channel, target in targets:
        channel_norm = channel.upper()
        if channel_norm not in {"WHATSAPP", "EMAIL", "CALL"}:
            continue
        if not _cooldown_ok(alert, channel_norm, now):
            continue
        exists = (
            db.query(NotificationOutbox)
            .filter(
                NotificationOutbox.alert_id == alert.public_id,
                NotificationOutbox.kind == "ALERT",
                NotificationOutbox.channel == channel_norm,
                NotificationOutbox.target == target,
            )
            .first()
        )
        if exists:
            continue
        if channel_norm == "EMAIL":
            subject = content.email_subject
            message = content.email_body
        elif channel_norm == "WHATSAPP":
            subject = None
            message = content.whatsapp_text
        else:
            subject = None
            message = content.call_script
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
        db.add(alert)  # persist token fields (and any updated_at)
        db.commit()
    return created


def enqueue_report_notifications(
    db: Session,
    report_id: str,
    *,
    subject: str,
    message: str,
) -> int:
    targets = resolve_notification_targets(db, godown_id=None, scopes=("HQ",))
    created = 0
    for channel, target in targets:
        channel_norm = channel.upper()
        if channel_norm not in {"EMAIL"}:
            continue
        outbox = NotificationOutbox(
            kind="REPORT",
            alert_id=None,
            report_id=report_id,
            channel=channel_norm,
            target=target,
            subject=subject,
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
