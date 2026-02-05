"""
Outbox worker for sending notifications with retries.
"""

from __future__ import annotations

import datetime
import html
import json
import logging
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Optional
from urllib.parse import urlparse
from ..core.config import settings
from ..integrations.twilio_client import get_twilio_messaging_client, get_twilio_voice_client
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.notification_outbox import NotificationOutbox
from ..models.event import Alert


logger = logging.getLogger("notification_worker")


class NotificationProvider:
    def send_whatsapp(self, to: str, message: str, media_url: Optional[str] = None) -> Optional[str]:
        raise NotImplementedError

    def send_email(self, to: str, subject: str, html: str) -> Optional[str]:
        raise NotImplementedError

    def send_call(self, to: str, message: str) -> Optional[str]:
        raise NotImplementedError


class WhatsAppLogProvider(NotificationProvider):
    def send_whatsapp(self, to: str, message: str, media_url: Optional[str] = None) -> Optional[str]:
        logging.getLogger("notifications").info("Log WhatsApp to=%s message=%s media=%s", to, message, media_url)
        return None

    def send_email(self, to: str, subject: str, html: str) -> Optional[str]:
        return None

    def send_call(self, to: str, message: str) -> Optional[str]:
        logging.getLogger("notifications").info("Log call to=%s message=%s", to, message)
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

    def send_call(self, to: str, message: str) -> Optional[str]:
        return None

class WhatsAppTwilioProvider(NotificationProvider):
    def __init__(self) -> None:
        self.from_whatsapp = (
            settings.TWILIO_WHATSAPP_FROM or os.getenv("TWILIO_WHATSAPP_FROM")
        )
        if not self.from_whatsapp:
            raise RuntimeError("Twilio WhatsApp 'from' number is missing (TWILIO_WHATSAPP_FROM).")
        self.client = get_twilio_messaging_client()

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

    def send_call(self, to: str, message: str) -> Optional[str]:
        logging.getLogger("notifications").info("Log call to=%s message=%s", to, message)
        return None


class CallLogProvider(NotificationProvider):
    def send_whatsapp(self, to: str, message: str, media_url: Optional[str] = None) -> Optional[str]:
        return None

    def send_email(self, to: str, subject: str, html: str) -> Optional[str]:
        return None

    def send_call(self, to: str, message: str) -> Optional[str]:
        logging.getLogger("notifications").info("Log call to=%s message=%s", to, message)
        return None


class TwilioCallProvider(NotificationProvider):
    """
    Twilio Voice call using TwiML or a webhook.

    Env:
        TWILIO_VOICE_ACCOUNT_SID
        TWILIO_VOICE_AUTH_TOKEN
        TWILIO_VOICE_FROM
        TWILIO_VOICE_WEBHOOK_URL
        TWILIO_CALL_VOICE         (default alice)
        TWILIO_CALL_LANGUAGE      (default en-US)
        TWILIO_CALL_TIMEOUT       (default 15)
    """

    def __init__(self) -> None:
        self.from_number = (
            settings.TWILIO_VOICE_FROM or os.getenv("TWILIO_CALL_FROM_NUMBER", "")
        ).strip()
        if not self.from_number:
            raise RuntimeError("Twilio voice 'from' number is missing (TWILIO_VOICE_FROM).")
        self.voice_webhook = (
            settings.TWILIO_VOICE_WEBHOOK_URL or os.getenv("TWILIO_VOICE_WEBHOOK_URL")
        )
        self.voice = os.getenv("TWILIO_CALL_VOICE", "alice")
        self.language = os.getenv("TWILIO_CALL_LANGUAGE", "en-US")
        try:
            self.timeout = int(os.getenv("TWILIO_CALL_TIMEOUT", "15"))
        except ValueError:
            self.timeout = 15

        self.client = get_twilio_voice_client()

    def send_whatsapp(self, to: str, message: str, media_url: Optional[str] = None) -> Optional[str]:
        return None

    def send_email(self, to: str, subject: str, html: str) -> Optional[str]:
        return None

    def send_call(self, to: str, message: str) -> Optional[str]:
        body = " ".join((message or "").split()) or "PDS Netra alert."
        escaped = html.escape(body)
        twiml = f"<Response><Say voice=\"{self.voice}\" language=\"{self.language}\">{escaped}</Say></Response>"

        params: dict[str, str] = {"to": to, "from_": self.from_number}
        if self.voice_webhook:
            params["url"] = self.voice_webhook
        else:
            params["twiml"] = twiml

        try:
            call = self.client.calls.create(**params)
            logging.getLogger("notifications").info(
                "Twilio call sent to=%s from=%s sid=%s",
                to,
                self.from_number,
                getattr(call, "sid", None),
            )
            return getattr(call, "sid", None)
        except Exception as exc:
            logging.getLogger("notifications").exception("Twilio call failed: %s", exc)
            raise RuntimeError(f"Twilio call failed: {exc}") from exc


class EmailSMTPProvider(NotificationProvider):
    """
    SMTP email provider.

    For MailHog:
        SMTP_HOST=127.0.0.1
        SMTP_PORT=1025
        SMTP_STARTTLS=false
    """

    def __init__(self) -> None:
        self.host = os.getenv("SMTP_HOST") or getattr(settings, "smtp_host", None)
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.user = os.getenv("SMTP_USER")
        self.password = os.getenv("SMTP_PASS") or os.getenv("SMTP_PASSWORD")
        self.sender = os.getenv("SMTP_FROM", self.user or "pds-netra@localhost")

        # Respect explicit flags first.
        raw_tls = os.getenv("SMTP_USE_TLS", os.getenv("SMTP_STARTTLS", "")).lower().strip()
        if raw_tls in {"0", "false", "no"}:
            self.starttls = False
        elif raw_tls in {"1", "true", "yes"}:
            self.starttls = True
        else:
            # Safe default: if port looks like MailHog(1025), don't use TLS
            self.starttls = False if self.port == 1025 else True

        logging.getLogger("notification_worker").info(
            "SMTP config loaded host=%s port=%s starttls=%s",
            self.host,
            self.port,
            self.starttls,
        )

    def send_whatsapp(self, to: str, message: str, media_url: Optional[str] = None) -> Optional[str]:
        return None

    def send_email(self, to: str, subject: str, html: str) -> Optional[str]:
        if not self.host:
            raise RuntimeError("SMTP_HOST is not configured")
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = to
        msg.set_content("PDS Netra notification")         # plain text fallback
        msg.add_alternative(html, subtype="html")         # html

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

    def send_call(self, to: str, message: str) -> Optional[str]:
        return None


@dataclass
class ProviderSet:
    whatsapp: NotificationProvider
    email: NotificationProvider
    call: NotificationProvider

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
        if outbox.channel == "CALL":
            return self.call.send_call(outbox.target, outbox.message)
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
    # WhatsApp (keep as-is)
    provider = (os.getenv("WHATSAPP_PROVIDER", "") or "").lower().strip()
    http_url = (os.getenv("WHATSAPP_HTTP_URL") or os.getenv("WHATSAPP_WEBHOOK_URL") or "").strip()

    if not provider:
        provider = "http" if http_url else "log"

    if provider == "twilio":
        whatsapp = WhatsAppTwilioProvider()
    elif provider in {"http", "meta"}:
        token = (os.getenv("WHATSAPP_HTTP_TOKEN") or "").strip()
        whatsapp = WhatsAppHttpProvider(http_url or "", token or None)
    else:
        whatsapp = WhatsAppLogProvider()

    # Email (GUARANTEED via settings.env_file)
    smtp_host = (os.getenv("SMTP_HOST") or "").strip()
    if not smtp_host:
        # Force load config/env_file (settings is created from env_file absolute path)
        _ = settings
        smtp_host = (os.getenv("SMTP_HOST") or "").strip()

    # If you want MailHog always, DO NOT silently fall back
    if not smtp_host:
        raise RuntimeError(
            "SMTP_HOST is not set in this worker process. "
            "Worker would use EmailLogProvider. Fix .env loading / start worker from backend."
        )

    email = EmailSMTPProvider()

    # Call (Twilio)
    sid = (
        settings.TWILIO_VOICE_ACCOUNT_SID
        or os.getenv("TWILIO_ACCOUNT_SID")
        or ""
    ).strip()
    token = (
        settings.TWILIO_VOICE_AUTH_TOKEN
        or os.getenv("TWILIO_AUTH_TOKEN")
        or ""
    ).strip()
    from_number = (
        settings.TWILIO_VOICE_FROM
        or os.getenv("TWILIO_CALL_FROM_NUMBER")
        or ""
    ).strip()

    missing = []
    if not sid:
        missing.append("TWILIO_ACCOUNT_SID")
    if not token:
        missing.append("TWILIO_AUTH_TOKEN")
    if not from_number:
        missing.append("TWILIO_CALL_FROM_NUMBER")

    if not missing:
        call_provider: NotificationProvider = TwilioCallProvider()
    else:
        logging.getLogger("notification_worker").warning(
            "Twilio CALL disabled (missing env): %s", ", ".join(missing)
        )
        call_provider = CallLogProvider()

    # 🔥 Very important log: tells you exactly what providers are active
    logging.getLogger("notification_worker").info(
        "Providers selected: whatsapp=%s email=%s call=%s",
        type(whatsapp).__name__,
        type(email).__name__,
        type(call_provider).__name__,
    )

    return ProviderSet(whatsapp=whatsapp, email=email, call=call_provider)

    


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
    # Build providers once per worker lifetime (pass providers from app/worker.py),
    # but keep this fallback for safety.
    providers = providers or _build_providers()
    now = datetime.datetime.now(datetime.timezone.utc)

    query = (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.status.in_(["PENDING", "RETRYING"]),
            or_(NotificationOutbox.next_retry_at.is_(None), NotificationOutbox.next_retry_at <= now),
        )
        .order_by(NotificationOutbox.created_at.asc())
        .limit(batch_size)
    )
    if db.bind and db.bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)

    rows = query.all()
    processed = 0

    for row in rows:
        # Mark retrying
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

        # Send
        try:
            message_id = providers.send(row)
            if row.channel == "EMAIL" and isinstance(providers.email, EmailLogProvider):
                raise RuntimeError("EMAIL provider is EmailLogProvider (SMTP_HOST not loaded).")
            if row.channel == "CALL" and not message_id:
                raise RuntimeError(
                    "CALL provider returned no SID. Twilio env likely missing, so CallLogProvider was used."
                )

            row.status = "SENT"
            row.provider_message_id = message_id
            now_sent = datetime.datetime.now(datetime.timezone.utc)
            row.sent_at = now_sent
            row.provider_message_id = message_id
            row.last_error = None
            row.next_retry_at = None
            if row.alert_id:
                alert = (
                    db.query(Alert)
                    .filter(Alert.public_id == row.alert_id)
                    .first()
                )
                if alert:
                    if row.channel == "WHATSAPP":
                        alert.last_whatsapp_at = now_sent
                    elif row.channel == "CALL":
                        alert.last_call_at = now_sent
                    elif row.channel == "EMAIL":
                        alert.last_email_at = now_sent
                    db.add(alert)
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

        # Persist result
        try:
            db.add(row)
            db.commit()
            processed += 1
        except Exception as exc:
            db.rollback()
            logger.warning("Failed to update outbox id=%s err=%s", row.id, exc)

    return processed
