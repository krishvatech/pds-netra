"""
Outbox worker for sending notifications with retries.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import smtplib
import urllib.request
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.notification_outbox import NotificationOutbox


logger = logging.getLogger("notification_worker")


class NotificationProvider:
    def send_whatsapp(self, to: str, message: str, media_url: Optional[str] = None) -> Optional[str]:
        raise NotImplementedError

    def send_email(self, to: str, subject: str, html: str) -> Optional[str]:
        raise NotImplementedError


class WhatsAppLogProvider(NotificationProvider):
    def send_whatsapp(self, to: str, message: str, media_url: Optional[str] = None) -> Optional[str]:
        logging.getLogger("notifications").info("Log WhatsApp to=%s message=%s media=%s", to, message, media_url)
        return None

    def send_email(self, to: str, subject: str, html: str) -> Optional[str]:
        return None


class WhatsAppHttpProvider(NotificationProvider):
    def __init__(self, url: str, token: Optional[str]) -> None:
        self.url = url
        self.token = token

    def send_whatsapp(self, to: str, message: str, media_url: Optional[str] = None) -> Optional[str]:
        if not self.url:
            raise RuntimeError("WHATSAPP_HTTP_URL is not configured")
        payload = {"to": to, "message": message, "media_url": media_url}
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = resp.read().decode("utf-8")
            try:
                payload = json.loads(data)
                return payload.get("message_id") or payload.get("id")
            except Exception:
                return None
        except Exception as exc:
            raise RuntimeError(f"WhatsApp HTTP send failed: {exc}") from exc

    def send_email(self, to: str, subject: str, html: str) -> Optional[str]:
        return None

class WhatsAppTwilioProvider(NotificationProvider):
    def __init__(self) -> None:
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_whatsapp = os.getenv("TWILIO_WHATSAPP_FROM")

        if not self.account_sid or not self.auth_token or not self.from_whatsapp:
            raise RuntimeError(
                "Twilio WhatsApp config missing. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM."
            )

        try:
            from twilio.rest import Client  # type: ignore
        except Exception as exc:
            raise RuntimeError("Twilio SDK not installed. Run: pip install twilio") from exc

        self.client = Client(self.account_sid, self.auth_token)

    def _normalize_to(self, to: str) -> str:
        t = (to or "").strip()
        if not t:
            raise RuntimeError("WhatsApp target is empty")
        if t.startswith("whatsapp:"):
            return t
        if t.startswith("+"):
            return f"whatsapp:{t}"
        return f"whatsapp:+{t}"

    def send_whatsapp(self, to: str, message: str, media_url: Optional[str] = None) -> Optional[str]:
        kwargs = {
            "from_": self.from_whatsapp,
            "to": self._normalize_to(to),
            "body": message,
        }
        if media_url:
            kwargs["media_url"] = [media_url]
        msg = self.client.messages.create(**kwargs)
        return getattr(msg, "sid", None)

    def send_email(self, to: str, subject: str, html: str) -> Optional[str]:
        return None

class EmailLogProvider(NotificationProvider):
    def send_whatsapp(self, to: str, message: str, media_url: Optional[str] = None) -> Optional[str]:
        return None

    def send_email(self, to: str, subject: str, html: str) -> Optional[str]:
        logging.getLogger("notifications").info("Log Email to=%s subject=%s", to, subject)
        return None


class EmailSMTPProvider(NotificationProvider):
    def __init__(self) -> None:
        self.host = os.getenv("SMTP_HOST")
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.user = os.getenv("SMTP_USER")
        self.password = os.getenv("SMTP_PASS") or os.getenv("SMTP_PASSWORD")
        self.sender = os.getenv("SMTP_FROM", self.user or "pds-netra@localhost")
        self.starttls = os.getenv("SMTP_USE_TLS", os.getenv("SMTP_STARTTLS", "true")).lower() in {"1", "true", "yes"}

    def send_whatsapp(self, to: str, message: str, media_url: Optional[str] = None) -> Optional[str]:
        return None

    def send_email(self, to: str, subject: str, html: str) -> Optional[str]:
        if not self.host:
            raise RuntimeError("SMTP_HOST is not configured")
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = to
        msg.set_content(html, subtype="html")
        try:
            with smtplib.SMTP(self.host, self.port, timeout=8) as server:
                server.ehlo()
                if self.starttls:
                    server.starttls()
                    server.ehlo()
                if self.user and self.password:
                    server.login(self.user, self.password)
                server.send_message(msg)
            return None
        except Exception as exc:
            raise RuntimeError(f"SMTP send failed: {exc}") from exc


@dataclass
class ProviderSet:
    whatsapp: NotificationProvider
    email: NotificationProvider

    def send(self, outbox: NotificationOutbox) -> Optional[str]:
        if outbox.channel == "WHATSAPP":
            media_url = outbox.media_url
            # Avoid media URLs that are only reachable locally (Twilio can't fetch them).
            if _is_local_media_url(media_url):
                media_url = None
            return self.whatsapp.send_whatsapp(outbox.target, outbox.message, media_url)
        if outbox.channel == "EMAIL":
            subject = outbox.subject or "PDS Netra Alert"
            return self.email.send_email(outbox.target, subject, outbox.message)
        raise RuntimeError(f"Unsupported channel: {outbox.channel}")


def _is_local_media_url(url: Optional[str]) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
    except Exception:
        return False
    return host in {"localhost", "127.0.0.1", "0.0.0.0"} or host.startswith("127.")


def _build_providers() -> ProviderSet:
    provider = os.getenv("WHATSAPP_PROVIDER", "").lower()
    http_url = os.getenv("WHATSAPP_HTTP_URL") or os.getenv("WHATSAPP_WEBHOOK_URL")

    if not provider:
        provider = "http" if http_url else "log"

    if provider == "twilio":
        whatsapp = WhatsAppTwilioProvider()
    elif provider in {"http", "meta"}:
        whatsapp = WhatsAppHttpProvider(http_url or "", os.getenv("WHATSAPP_HTTP_TOKEN"))
    else:
        whatsapp = WhatsAppLogProvider()

    email_provider = "smtp" if os.getenv("SMTP_HOST") else "log"
    email = EmailSMTPProvider() if email_provider == "smtp" else EmailLogProvider()
    return ProviderSet(whatsapp=whatsapp, email=email)


def _backoff_seconds(attempt: int) -> int:
    schedule = [60, 300, 900, 3600, 21600]
    idx = min(max(attempt - 1, 0), len(schedule) - 1)
    return schedule[idx]


def process_outbox_batch(
    db: Session,
    *,
    providers: Optional[ProviderSet] = None,
    max_attempts: int = 5,
    batch_size: int = 50,
) -> int:
    providers = providers or _build_providers()
    now = datetime.datetime.now(datetime.timezone.utc)
    query = db.query(NotificationOutbox).filter(
        NotificationOutbox.status.in_(["PENDING", "RETRYING"]),
        or_(NotificationOutbox.next_retry_at.is_(None), NotificationOutbox.next_retry_at <= now),
    ).order_by(NotificationOutbox.created_at.asc()).limit(batch_size)
    if db.bind and db.bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    rows = query.all()
    processed = 0
    for row in rows:
        try:
            row.attempts = int(row.attempts or 0) + 1
            row.status = "RETRYING"
            row.next_retry_at = now + datetime.timedelta(seconds=30)
            row.updated_at = now
            db.add(row)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("Failed to mark outbox retrying id=%s err=%s", row.id, exc)
            continue

        try:
            message_id = providers.send(row)
            row.status = "SENT"
            row.sent_at = datetime.datetime.now(datetime.timezone.utc)
            row.provider_message_id = message_id
            row.last_error = None
            row.next_retry_at = None
        except Exception as exc:
            row.last_error = str(exc)
            if row.attempts >= max_attempts:
                row.status = "FAILED"
                row.next_retry_at = None
            else:
                row.status = "RETRYING"
                row.next_retry_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                    seconds=_backoff_seconds(row.attempts)
                )
        try:
            db.add(row)
            db.commit()
            processed += 1
        except Exception as exc:
            db.rollback()
            logger.warning("Failed to update outbox id=%s err=%s", row.id, exc)
    return processed
