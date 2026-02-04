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
    call_script: str
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


META_FIELD_LABELS: list[tuple[str, str]] = [
    ("vehicle_plate", "Vehicle plate"),
    ("plate_text", "Plate text"),
    ("plate_norm", "Plate (normalized)"),
    ("movement_type", "Movement type"),
    ("reason", "Reason"),
    ("detected_count", "Detected count"),
    ("occurred_at", "Occurred at"),
    ("last_seen_at", "Last seen at"),
    ("entry_at", "Entry at"),
    ("age_hours", "Age (h)"),
    ("threshold_hours", "Threshold (h)"),
    ("animal_species", "Animal species"),
    ("animal_count", "Animal count"),
    ("animal_confidence", "Animal confidence"),
    ("animal_is_night", "Animal is night"),
    ("fire_confidence", "Fire confidence"),
    ("fire_classes", "Fire classes"),
    ("fire_model_name", "Fire model"),
    ("fire_model_version", "Fire model version"),
    ("fire_weights_id", "Fire weights"),
    ("snapshot_url", "Snapshot URL"),
    ("clip_url", "Clip URL"),
]


def _format_meta_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, dict)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)
    return str(value)


def _collect_meta_values(event: Optional[Event], alert: Alert) -> dict[str, Any]:
    values: dict[str, Any] = {}
    sources: list[dict[str, Any]] = []
    if event and isinstance(event.meta, dict):
        sources.append(event.meta)
    extra = alert.extra if isinstance(alert.extra, dict) else {}
    if extra:
        sources.append(extra)
    for source in sources:
        for key, value in source.items():
            if value is None:
                continue
            values[key] = value
    return values


def _build_metadata_rows(
    *,
    alert: Alert,
    event: Optional[Event],
    camera: Camera | None,
    camera_name: str,
    godown_name: str,
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if alert.godown_id:
        rows.append(("Godown ID", alert.godown_id))
    if godown_name and godown_name != alert.godown_id:
        rows.append(("Godown name", godown_name))
    if camera_name:
        rows.append(("Camera label", camera_name))
    if alert.camera_id:
        rows.append(("Camera ID", alert.camera_id))
    if camera and camera.role:
        rows.append(("Camera role", camera.role))
    if alert.zone_id:
        rows.append(("Zone", alert.zone_id))
    if alert.summary:
        rows.append(("Summary", alert.summary))
    if alert.status:
        rows.append(("Status", alert.status))

    meta_values = _collect_meta_values(event, alert)
    if meta_values:
        for key, label in META_FIELD_LABELS:
            value = meta_values.pop(key, None)
            if value is not None:
                rows.append((label, _format_meta_value(value)))
        for key in sorted(meta_values):
            rows.append((key.replace("_", " ").title(), _format_meta_value(meta_values[key])))
    return rows


def _render_meta_table(rows: list[tuple[str, str]]) -> str:
    if not rows:
        return ""
    lines = [
        '<table style="border-collapse:collapse;margin-top:8px;">',
        "<tbody>",
    ]
    for label, value in rows:
        lines.append(
            "<tr>"
            f'<td style="padding:4px 8px;font-weight:600;border:1px solid #4b5563;background:#0f172a;color:#f8fafc;">{html.escape(label)}</td>'
            f'<td style="padding:4px 8px;border:1px solid #4b5563;background:#111827;color:#f8fafc;">{html.escape(value)}</td>'
            "</tr>"
        )
    lines.append("</tbody></table>")
    return "".join(lines)


def _build_call_script(segments: list[str]) -> str:
    normalized: list[str] = []
    for text in segments:
        text = text.strip()
        if not text:
            continue
        text = text.replace("\n", " ")
        normalized.append(" ".join(text.split()))
    script = ". ".join(normalized)
    script = " ".join(script.split())
    if script and not script.endswith("."):
        script += "."
    return script or "PDS Netra alert."
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
    camera = None
    if alert.camera_id:
        camera = (
            db.query(Camera)
            .filter(Camera.id == alert.camera_id, Camera.godown_id == alert.godown_id)
            .first()
        )
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

    call_segments = [
        f"{alert_title} at {godown_name}",
        f"Camera {camera_name} at {ts_str}",
        f"Details {details}",
    ]
    if evidence or link:
        call_segments.append("Evidence and dashboard links are available via email")
    call_script = _build_call_script(call_segments)

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
        call_script=call_script,
        media_url=evidence,
    )


# Helpers for normalizing and merging targets
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
        ep_scope = (ep.scope or "").upper()
        if ep_scope == "GODOWN":
            ep_scope = "GODOWN_MANAGER"
        if ep_scope == scope:
            if scope == "GODOWN_MANAGER":
                if godown_id and ep.godown_id == godown_id:
                    normalized = _normalize_target(ep.channel, ep.target)
                    if normalized:
                        targets.append(normalized)
            else:
                normalized = _normalize_target(ep.channel, ep.target)
                if normalized:
                    targets.append(normalized)
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
                    normalized = _normalize_target(row.channel, row.destination)
                    if normalized:
                        targets.append(normalized)
            else:
                normalized = _normalize_target(row.channel, row.destination)
                if normalized:
                    targets.append(normalized)
    return targets


def _recipient_targets_from_env(*, godown_id: Optional[str], scope: str) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    if scope == "HQ":
        hq_emails = [e.strip() for e in os.getenv("WATCHLIST_NOTIFY_HQ_EMAILS", "").split(",") if e.strip()]
        hq_whatsapp = [e.strip() for e in os.getenv("WATCHLIST_NOTIFY_HQ_WHATSAPP", "").split(",") if e.strip()]
        hq_calls = [e.strip() for e in os.getenv("WATCHLIST_NOTIFY_HQ_CALLS", "").split(",") if e.strip()]
        for email in hq_emails:
            normalized = _normalize_target("EMAIL", email)
            if normalized:
                targets.append(normalized)
        for phone in hq_whatsapp:
            normalized = _normalize_target("WHATSAPP", phone)
            if normalized:
                targets.append(normalized)
        for phone in hq_calls:
            normalized = _normalize_target("CALL", phone)
            if normalized:
                targets.append(normalized)
    if scope == "GODOWN_MANAGER" and godown_id:
        mapping = os.getenv("WATCHLIST_NOTIFY_GODOWN_EMAILS", "")
        targets += _parse_mapping(mapping, godown_id, channel="EMAIL")
        mapping = os.getenv("WATCHLIST_NOTIFY_GODOWN_WHATSAPP", "")
        targets += _parse_mapping(mapping, godown_id, channel="WHATSAPP")
        mapping = os.getenv("WATCHLIST_NOTIFY_GODOWN_CALLS", "")
        targets += _parse_mapping(mapping, godown_id, channel="CALL")
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
            normalized = _normalize_target(channel, dest.strip())
            if normalized:
                targets.append(normalized)
    return targets


def resolve_notification_targets(
    db: Session,
    *,
    godown_id: Optional[str],
    scopes: Iterable[str],
) -> list[tuple[str, str]]:
    endpoints = db.query(NotificationEndpoint).all()
    recipients = db.query(NotificationRecipient).all()
    target_sources: list[list[tuple[str, str]]] = []
    for scope in scopes:
        target_sources.append(_targets_from_endpoints(endpoints, godown_id=godown_id, scope=scope))
        target_sources.append(_targets_from_recipients(recipients, godown_id=godown_id, scope=scope))
        target_sources.append(_recipient_targets_from_env(godown_id=godown_id, scope=scope))
    targets = _merge_targets(*target_sources)
    return targets


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
    targets = resolve_notification_targets(
        db,
        godown_id=alert.godown_id,
        scopes=("GODOWN_MANAGER", "HQ"),
    )
    if not targets:
        logger.info("No notification targets configured for godown=%s", alert.godown_id)
        return 0
    event = _find_event_for_alert(db, alert, event)
    content = build_alert_notification(db, alert, event)
    created = 0
    for channel, target in targets:
        channel_norm = channel.upper()
        if channel_norm not in {"WHATSAPP", "EMAIL", "CALL"}:
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
    targets = resolve_notification_targets(
        db,
        godown_id=None,
        scopes=("HQ",),
    )
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
