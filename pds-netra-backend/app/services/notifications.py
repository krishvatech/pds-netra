"""
Notification helpers for alerts (webhooks + email + WhatsApp).
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
import urllib.request
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from ..models.event import Alert, Event
from ..models.notification_recipient import NotificationRecipient
from .notification_outbox import enqueue_alert_notifications
from ..core.config import settings


def _webhook_urls() -> list[str]:
    urls = os.getenv("NOTIFY_WEBHOOK_URLS", "") or os.getenv("NOTIFY_WEBHOOK_URL", "")
    if not urls:
        return []
    return [u.strip() for u in urls.split(",") if u.strip()]


def _send_webhook(payload: dict) -> None:
    urls = _webhook_urls()
    if not urls:
        return
    body = json.dumps(payload).encode("utf-8")
    for url in urls:
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3):
                pass
        except Exception as exc:
            logging.getLogger("notifications").warning("Webhook notify failed (%s): %s", url, exc)


def _send_email(payload: dict) -> None:
    host = os.getenv("SMTP_HOST")
    if not host:
        return
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM", user or "pds-netra@localhost")
    to_raw = os.getenv("SMTP_TO", "")
    recipients = [e.strip() for e in to_raw.split(",") if e.strip()]
    if not recipients:
        return
    msg = EmailMessage()
    msg["Subject"] = f"PDS Netra Alert: {payload.get('alert_type')}"
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(json.dumps(payload, indent=2))
    try:
        with smtplib.SMTP(host, port, timeout=5) as server:
            server.ehlo()
            if os.getenv("SMTP_STARTTLS", "true").lower() in {"1", "true", "yes"}:
                server.starttls()
                server.ehlo()
            if user and password:
                server.login(user, password)
            server.send_message(msg)
    except Exception as exc:
        logging.getLogger("notifications").warning("Email notify failed: %s", exc)


def notify_alert(db: Session, alert: Alert, event: Optional[Event] = None) -> None:
    try:
        enqueue_alert_notifications(db, alert, event=event)
    except Exception as exc:
        logging.getLogger("notifications").warning("Failed to enqueue notifications: %s", exc)


@dataclass
class NotificationTarget:
    channel: str
    destination: str


class NotificationProvider:
    def send_whatsapp(self, to: str, message: str, media_url: Optional[str] = None) -> None:
        raise NotImplementedError

    def send_email(self, to: str, subject: str, html: str) -> None:
        raise NotImplementedError


class MockNotificationProvider(NotificationProvider):
    def send_whatsapp(self, to: str, message: str, media_url: Optional[str] = None) -> None:
        logging.getLogger("notifications").info("Mock WhatsApp to=%s message=%s media=%s", to, message, media_url)

    def send_email(self, to: str, subject: str, html: str) -> None:
        logging.getLogger("notifications").info("Mock Email to=%s subject=%s", to, subject)


class WebhookWhatsAppProvider(NotificationProvider):
    def __init__(self) -> None:
        self.url = os.getenv("WHATSAPP_WEBHOOK_URL")

    def send_whatsapp(self, to: str, message: str, media_url: Optional[str] = None) -> None:
        if not self.url:
            return
        payload = {"to": to, "message": message, "media_url": media_url}
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception as exc:
            logging.getLogger("notifications").warning("WhatsApp webhook failed: %s", exc)

    def send_email(self, to: str, subject: str, html: str) -> None:
        return


class SmtpEmailProvider(NotificationProvider):
    def __init__(self) -> None:
        self.host = os.getenv("SMTP_HOST")
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.user = os.getenv("SMTP_USER")
        self.password = os.getenv("SMTP_PASSWORD")
        self.sender = os.getenv("SMTP_FROM", self.user or "pds-netra@localhost")
        self.starttls = os.getenv("SMTP_STARTTLS", "true").lower() in {"1", "true", "yes"}

    def send_whatsapp(self, to: str, message: str, media_url: Optional[str] = None) -> None:
        return

    def send_email(self, to: str, subject: str, html: str) -> None:
        if not self.host:
            return
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = to
        msg.set_content(html)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=5) as server:
                server.ehlo()
                if self.starttls:
                    server.starttls()
                    server.ehlo()
                if self.user and self.password:
                    server.login(self.user, self.password)
                server.send_message(msg)
        except Exception as exc:
            logging.getLogger("notifications").warning("SMTP notify failed: %s", exc)


class NotificationService:
    def __init__(self, providers: Iterable[NotificationProvider]) -> None:
        self.providers = list(providers)

    def send_whatsapp(self, to: str, message: str, media_url: Optional[str] = None) -> None:
        for provider in self.providers:
            try:
                provider.send_whatsapp(to, message, media_url)
            except Exception as exc:
                logging.getLogger("notifications").warning("WhatsApp provider failed: %s", exc)

    def send_email(self, to: str, subject: str, html: str) -> None:
        for provider in self.providers:
            try:
                provider.send_email(to, subject, html)
            except Exception as exc:
                logging.getLogger("notifications").warning("Email provider failed: %s", exc)


def _parse_mapping(raw: str, godown_id: str, channel: str) -> list[NotificationTarget]:
    targets: list[NotificationTarget] = []
    for item in raw.split(";"):
        if ":" not in item:
            continue
        gid, dests = item.split(":", 1)
        if gid.strip() != godown_id:
            continue
        for dest in dests.split(","):
            dest = dest.strip()
            if dest:
                targets.append(NotificationTarget(channel=channel, destination=dest))
    return targets


def _recipient_targets_from_env(godown_id: Optional[str]) -> list[NotificationTarget]:
    targets: list[NotificationTarget] = []
    hq_emails = [e.strip() for e in os.getenv("WATCHLIST_NOTIFY_HQ_EMAILS", "").split(",") if e.strip()]
    hq_whatsapp = [e.strip() for e in os.getenv("WATCHLIST_NOTIFY_HQ_WHATSAPP", "").split(",") if e.strip()]
    for email in hq_emails:
        targets.append(NotificationTarget(channel="EMAIL", destination=email))
    for phone in hq_whatsapp:
        targets.append(NotificationTarget(channel="WHATSAPP", destination=phone))
    if godown_id:
        mapping = os.getenv("WATCHLIST_NOTIFY_GODOWN_EMAILS", "")
        targets += _parse_mapping(mapping, godown_id, channel="EMAIL")
        mapping = os.getenv("WATCHLIST_NOTIFY_GODOWN_WHATSAPP", "")
        targets += _parse_mapping(mapping, godown_id, channel="WHATSAPP")
    return targets


def _load_recipients(db: Session, godown_id: Optional[str]) -> list[NotificationTarget]:
    rows = db.query(NotificationRecipient).all()
    if not rows:
        return _recipient_targets_from_env(godown_id)
    targets: list[NotificationTarget] = []
    for row in rows:
        if row.godown_id and godown_id and row.godown_id != godown_id:
            continue
        targets.append(NotificationTarget(channel=row.channel, destination=row.destination))
    return targets


def _build_notification_service() -> NotificationService:
    _ = settings  # ensure .env is loaded before checking providers
    providers: list[NotificationProvider] = []
    if os.getenv("WHATSAPP_WEBHOOK_URL"):
        providers.append(WebhookWhatsAppProvider())
    if settings.smtp_host:
        providers.append(SmtpEmailProvider())
    if not providers:
        providers.append(MockNotificationProvider())
    return NotificationService(providers)


def notify_blacklist_alert(
    db: Session,
    alert: Alert,
    *,
    person_name: Optional[str],
    match_score: Optional[float],
    snapshot_url: Optional[str],
) -> None:
    try:
        enqueue_alert_notifications(db, alert)
    except Exception as exc:
        logging.getLogger("notifications").warning("Failed to enqueue blacklist alert: %s", exc)


def notify_after_hours_alert(
    db: Session,
    alert: Alert,
    *,
    count: Optional[int],
    plate: Optional[str],
    snapshot_url: Optional[str],
) -> None:
    try:
        enqueue_alert_notifications(db, alert)
    except Exception as exc:
        logging.getLogger("notifications").warning("Failed to enqueue after-hours alert: %s", exc)


def notify_animal_intrusion(
    db: Session,
    alert: Alert,
    *,
    species: Optional[str],
    count: Optional[int],
    snapshot_url: Optional[str],
    is_night: Optional[bool],
) -> None:
    try:
        enqueue_alert_notifications(db, alert)
    except Exception as exc:
        logging.getLogger("notifications").warning("Failed to enqueue animal alert: %s", exc)


def notify_dispatch_movement_delay(
    db: Session,
    alert: Alert,
    *,
    plate: Optional[str],
    threshold_hours: int,
    age_hours: float,
    snapshot_url: Optional[str],
) -> None:
    try:
        enqueue_alert_notifications(db, alert)
    except Exception as exc:
        logging.getLogger("notifications").warning("Failed to enqueue dispatch delay alert: %s", exc)


def notify_fire_detected(
    db: Session,
    alert: Alert,
    *,
    classes: Optional[list[str]],
    confidence: Optional[float],
    snapshot_url: Optional[str],
) -> None:
    try:
        enqueue_alert_notifications(db, alert)
    except Exception as exc:
        logging.getLogger("notifications").warning("Failed to enqueue fire alert: %s", exc)
