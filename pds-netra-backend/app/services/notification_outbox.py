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
    details_display = details or "-"
    evidence_safe = _safe(evidence) if evidence else ""
    email_body = (
        "<div style=\"font-family: 'Segoe UI', Arial, sans-serif; background:#f5f7fb; padding:20px;\">"
        "<div style=\"max-width:640px; margin:0 auto; background:#ffffff; border:1px solid #e5e7eb; border-radius:12px; overflow:hidden;\">"
        "<div style=\"background:#0f172a; color:#ffffff; padding:16px 20px;\">"
        "<div style=\"font-size:12px; letter-spacing:0.12em; text-transform:uppercase; opacity:0.7;\">PDS Netra Alert</div>"
        f"<div style=\"font-size:20px; font-weight:700; margin-top:4px;\">{_safe(alert_title)}</div>"
        "</div>"
        "<div style=\"padding:20px;\">"
        f"<p style=\"margin:0 0 14px 0; font-size:14px; color:#0f172a;\"><strong>Details:</strong> {_safe(details_display)}</p>"
        "<table style=\"width:100%; border-collapse:collapse; font-size:14px; color:#0f172a;\">"
        "<tr>"
        "<td style=\"padding:8px 0; color:#64748b; width:120px;\">Godown</td>"
        f"<td style=\"padding:8px 0; font-weight:600;\">{_safe(godown_label)}</td>"
        "</tr>"
        "<tr>"
        "<td style=\"padding:8px 0; color:#64748b;\">Camera</td>"
        f"<td style=\"padding:8px 0; font-weight:600;\">{_safe(cam_label)}</td>"
        "</tr>"
        "<tr>"
        "<td style=\"padding:8px 0; color:#64748b;\">Time</td>"
        f"<td style=\"padding:8px 0; font-weight:600;\">{_safe(_format_ts(alert.start_time))}</td>"
        "</tr>"
        "</table>"
    )
    if evidence:
        email_body += (
            "<div style=\"margin-top:16px; padding:12px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px;\">"
            "<div style=\"font-size:13px; color:#0f172a; margin-bottom:8px;\"><strong>Evidence</strong></div>"
            f"<a href=\"{evidence_safe}\" style=\"display:inline-block; background:#2563eb; color:#ffffff; text-decoration:none; padding:8px 12px; border-radius:8px; font-size:13px;\">View evidence</a>"
            f"<div style=\"margin-top:8px; font-size:12px; color:#64748b; word-break:break-all;\">{evidence_safe}</div>"
            "</div>"
        )
    email_body += "</div></div></div>"
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
        email_body += (
            "<div style=\"max-width:640px; margin:12px auto 0; padding:0 20px;\">"
            f"<div style=\"font-size:12px; color:#64748b;\">Dashboard: <a href=\"{_safe(link)}\">{_safe(link)}</a></div>"
            "</div>"
        )

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
        # Backward/forward compatibility:
        # - Some schemas use `is_enabled`, some don't.
        # - Some schemas use `target`, others use `destination`.
        is_enabled = getattr(r, "is_enabled", True)
        if not is_enabled:
            continue
        recipient_target = getattr(r, "target", None) or getattr(r, "destination", None)
        norm = _normalize_target(getattr(r, "channel", None), recipient_target)
        if norm:
            targets.append(norm)
    return targets


def _parse_scoped_targets(raw: str, *, godown_id: Optional[str], channel: str) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    if not raw:
        return targets
    # Format: GDN_001:+911111111111,+922222222222;GDN_002:+933333333333
    for item in raw.split(";"):
        if ":" not in item:
            continue
        gid, dests = item.split(":", 1)
        if godown_id and gid.strip() != godown_id:
            continue
        for dest in dests.split(","):
            norm = _normalize_target(channel, dest)
            if norm:
                targets.append(norm)
    return targets


def _targets_from_env(*, godown_id: Optional[str], scopes: Iterable[str]) -> list[tuple[str, str]]:
    scope_set = {str(s).upper() for s in scopes}
    targets: list[tuple[str, str]] = []

    if "HQ" in scope_set:
        for value in (os.getenv("WATCHLIST_NOTIFY_HQ_EMAILS", "") or "").split(","):
            norm = _normalize_target("EMAIL", value)
            if norm:
                targets.append(norm)
        for value in (os.getenv("WATCHLIST_NOTIFY_HQ_WHATSAPP", "") or "").split(","):
            norm = _normalize_target("WHATSAPP", value)
            if norm:
                targets.append(norm)
        for value in (os.getenv("WATCHLIST_NOTIFY_HQ_CALLS", "") or "").split(","):
            norm = _normalize_target("CALL", value)
            if norm:
                targets.append(norm)

    if "GODOWN_MANAGER" in scope_set and godown_id:
        targets.extend(
            _parse_scoped_targets(
                os.getenv("WATCHLIST_NOTIFY_GODOWN_EMAILS", "") or "",
                godown_id=godown_id,
                channel="EMAIL",
            )
        )
        targets.extend(
            _parse_scoped_targets(
                os.getenv("WATCHLIST_NOTIFY_GODOWN_WHATSAPP", "") or "",
                godown_id=godown_id,
                channel="WHATSAPP",
            )
        )
        targets.extend(
            _parse_scoped_targets(
                os.getenv("WATCHLIST_NOTIFY_GODOWN_CALLS", "") or "",
                godown_id=godown_id,
                channel="CALL",
            )
        )
    return targets


def resolve_notification_targets(
    db: Session,
    *,
    godown_id: Optional[str],
    scopes: Iterable[str],
) -> list[tuple[str, str]]:
    scopes = tuple(scopes)
    endpoints = db.query(NotificationEndpoint).all()
    recipients = db.query(NotificationRecipient).all()
    targets: list[tuple[str, str]] = []
    for scope in scopes:
        targets.extend(_targets_from_endpoints(endpoints, godown_id=godown_id, scope=scope))
    targets = _merge_targets(
        targets,
        _targets_from_recipients(recipients),
        _targets_from_env(godown_id=godown_id, scopes=scopes),
    )
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
        ack_button = (
            "<div style=\"margin-top:12px; padding-top:12px; border-top:1px solid #e2e8f0;\">"
            "<div style=\"font-size:13px; color:#0f172a; margin-bottom:8px;\"><strong>Acknowledge</strong></div>"
            f"<a href=\"{_safe(ack_url)}\" style=\"display:inline-block; background:#ea580c; color:#ffffff; text-decoration:none; padding:8px 12px; border-radius:8px; font-size:13px;\">Acknowledge alert</a>"
            f"<div style=\"margin-top:8px; font-size:12px; color:#64748b; word-break:break-all;\">{_safe(ack_url)}</div>"
            "</div>"
        )
        if content.media_url:
            content.email_body = content.email_body.replace("</div></div></div>", f"{ack_button}</div></div></div>")
        else:
            content.email_body += (
                "<div style=\"max-width:640px; margin:12px auto 0; padding:0 20px;\">"
                "<div style=\"background:#fff7ed; border:1px solid #fed7aa; border-radius:10px; padding:12px;\">"
                "<div style=\"font-size:13px; color:#9a3412; margin-bottom:8px;\"><strong>Acknowledge</strong></div>"
                f"<a href=\"{_safe(ack_url)}\" style=\"display:inline-block; background:#ea580c; color:#ffffff; text-decoration:none; padding:8px 12px; border-radius:8px; font-size:13px;\">Acknowledge alert</a>"
                f"<div style=\"margin-top:8px; font-size:12px; color:#9a3412; word-break:break-all;\">{_safe(ack_url)}</div>"
                "</div>"
                "</div>"
            )

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
    message: Optional[str] = None,
    message_text: Optional[str] = None,
    email_html: Optional[str] = None,
    scopes: Iterable[str] = ("HQ",),
    godown_id: Optional[str] = None,
) -> int:
    targets = resolve_notification_targets(db, godown_id=godown_id, scopes=scopes)
    payload = email_html or message or message_text or ""
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
            message=payload,
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
