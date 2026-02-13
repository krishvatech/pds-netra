"""
Outbox worker for sending notifications with retries.
"""

from __future__ import annotations

import datetime
import html
import json
import logging
import os
import re
import smtplib
import requests
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Optional
from urllib.parse import urlparse
import urllib.request
import urllib.error
from ..core.config import settings
from ..integrations.twilio_client import get_twilio_voice_client
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


def _normalize_meta_whatsapp_target(target: str) -> str:
    raw = (target or "").strip()
    if not raw:
        raise RuntimeError("Meta WhatsApp target is empty")
    if raw.lower().startswith("whatsapp:"):
        raw = raw.split(":", 1)[1].strip()
    if raw.startswith("+"):
        raw = raw[1:]
    if not raw.isdigit() or len(raw) < 8:
        raise RuntimeError(f"Invalid WhatsApp target for Meta: {target!r}")
    return raw


def _post_meta_whatsapp_message(
    *,
    access_token: str,
    api_version: str,
    phone_number_id: str,
    payload: dict,
) -> dict:
    url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=(5, 20))
    except requests.RequestException as exc:
        raise RuntimeError(f"Meta WhatsApp request failed: {exc}") from exc

    if response.status_code // 100 != 2:
        detail = response.text
        try:
            err_json = response.json()
            error_obj = err_json.get("error") if isinstance(err_json, dict) else None
            if isinstance(error_obj, dict):
                detail = (
                    f"type={error_obj.get('type')} "
                    f"code={error_obj.get('code')} "
                    f"message={error_obj.get('message')}"
                )
        except Exception:
            pass
        raise RuntimeError(f"Meta WhatsApp send failed status={response.status_code} detail={detail}")

    try:
        return response.json()
    except Exception as exc:
        raise RuntimeError(f"Meta WhatsApp send succeeded but response was not JSON: {exc}") from exc


class WhatsAppMetaProvider(NotificationProvider):
    def __init__(self) -> None:
        self.access_token = (os.getenv("META_WA_ACCESS_TOKEN") or "").strip()
        self.phone_number_id = (os.getenv("META_WA_PHONE_NUMBER_ID") or "").strip()
        self.api_version = (os.getenv("META_WA_API_VERSION") or "v20.0").strip() or "v20.0"
        missing = []
        if not self.access_token:
            missing.append("META_WA_ACCESS_TOKEN")
        if not self.phone_number_id:
            missing.append("META_WA_PHONE_NUMBER_ID")
        if missing:
            raise RuntimeError(f"Meta WhatsApp disabled (missing env): {', '.join(missing)}")

    def send_whatsapp(self, to: str, message: str, media_url: Optional[str] = None) -> Optional[str]:
        target = _normalize_meta_whatsapp_target(to)
        msg = (message or "").strip()
        use_image = bool(media_url and str(media_url).startswith("https://"))
        payload: dict
        if use_image:
            payload = {
                "messaging_product": "whatsapp",
                "to": target,
                "type": "image",
                "image": {"link": media_url, "caption": msg[:900]},
            }
        else:
            payload = {
                "messaging_product": "whatsapp",
                "to": target,
                "type": "text",
                "text": {"body": msg},
            }

        logger.info("Meta WhatsApp send attempt to=%s mode=%s", target, "image" if use_image else "text")
        try:
            data = _post_meta_whatsapp_message(
                access_token=self.access_token,
                api_version=self.api_version,
                phone_number_id=self.phone_number_id,
                payload=payload,
            )
        except Exception as exc:
            logger.warning("Meta WhatsApp send failed to=%s err=%s", target, exc)
            raise

        messages = data.get("messages") if isinstance(data, dict) else None
        if isinstance(messages, list) and messages:
            first = messages[0]
            if isinstance(first, dict):
                return first.get("id")
        return None

    def send_email(self, to: str, subject: str, html: str) -> Optional[str]:
        return None

    def send_call(self, to: str, message: str) -> Optional[str]:
        return None


class WhatsAppUnavailableProvider(NotificationProvider):
    def __init__(self, reason: str) -> None:
        self.reason = reason

    def send_whatsapp(self, to: str, message: str, media_url: Optional[str] = None) -> Optional[str]:
        raise RuntimeError(self.reason)

    def send_email(self, to: str, subject: str, html: str) -> Optional[str]:
        return None

    def send_call(self, to: str, message: str) -> Optional[str]:
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
        # TwiML (no external URL required)
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
        msg.set_content("PDS Netra notification")  # plain text fallback

        # Try to inline the first external image so MailHog and clients with CSP show it.
        html_body = html
        related_bytes: Optional[bytes] = None
        related_type: Optional[str] = None
        related_subtype: Optional[str] = None
        related_cid: Optional[str] = None
        try:
            match = re.search(r"<img[^>]+src=[\"']([^\"']+)[\"']", html, flags=re.IGNORECASE)
            if match:
                src_url = match.group(1)
                if src_url.startswith("http://") or src_url.startswith("https://"):
                    with urllib.request.urlopen(src_url, timeout=6) as resp:
                        data = resp.read()
                        content_type = resp.headers.get_content_type()
                    # Guard against huge downloads (5 MB cap)
                    if data and len(data) <= 5 * 1024 * 1024 and content_type.startswith("image/"):
                        related_bytes = data
                        related_type, related_subtype = content_type.split("/", 1)
                        cid = make_msgid(domain="pdsnetra.local")
                        related_cid = cid
                        cid_ref = cid[1:-1]
                        html_body = html_body.replace(src_url, f"cid:{cid_ref}")
        except Exception as exc:
            logging.getLogger("notification_worker").warning("Inline image fetch failed: %s", exc)

        html_part = msg.add_alternative(html_body, subtype="html")
        if related_bytes and related_type and related_subtype and related_cid:
            html_part.add_related(related_bytes, maintype=related_type, subtype=related_subtype, cid=related_cid)

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
            media_url = _normalize_media_url(outbox.media_url)
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


def _normalize_media_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        parsed = urlparse(url)
    except Exception:
        return url
    if parsed.scheme and parsed.netloc and not _is_local_media_url(url):
        return url
    base = (os.getenv("MEDIA_PUBLIC_BASE_URL") or os.getenv("BACKEND_BASE_URL") or "").strip().rstrip("/")
    if not base:
        return url
    if _is_local_media_url(base):
        return url
    path = parsed.path or ""
    if not path.startswith("/"):
        path = f"/{path}"
    normalized = f"{base}{path}"
    if parsed.query:
        normalized = f"{normalized}?{parsed.query}"
    return normalized


def _build_providers() -> ProviderSet:
    logger = logging.getLogger("notification_worker")
    # WhatsApp (Meta Cloud API only)
    provider = (os.getenv("WHATSAPP_PROVIDER", "") or "").lower().strip()
    if not provider:
        provider = "meta"

    if provider == "meta":
        try:
            whatsapp = WhatsAppMetaProvider()
        except Exception as exc:
            reason = f"Meta WhatsApp unavailable: {exc}"
            logger.error(reason)
            whatsapp = WhatsAppUnavailableProvider(reason)
    else:
        reason = f"Unsupported WHATSAPP_PROVIDER={provider!r}. Only 'meta' is supported."
        logger.error(reason)
        whatsapp = WhatsAppUnavailableProvider(reason)

    # Email (GUARANTEED via settings.env_file)
    smtp_host = (os.getenv("SMTP_HOST") or "").strip()
    if not smtp_host:
        # Force load config/env_file (settings is created from env_file absolute path)
        _ = settings
        smtp_host = (os.getenv("SMTP_HOST") or "").strip()

    if not smtp_host:
        logger.error("SMTP_HOST missing; using EmailLogProvider.")
        email = EmailLogProvider()
    else:
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
        try:
            call_provider = TwilioCallProvider()
        except Exception as exc:
            logger.error("Twilio CALL disabled: %s", exc)
            call_provider = CallLogProvider()
    else:
        logger.error("Twilio CALL disabled (missing env): %s", ", ".join(missing))
        call_provider = CallLogProvider()

    # 🔥 Very important log: tells you exactly what providers are active
    logger.info(
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
        message_id: Optional[str] = None
        try:
            message_id = providers.send(row)

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
            logger.warning(
                "Notification send failed id=%s channel=%s target=%s alert_id=%s attempts=%s message_id=%s err=%s",
                row.id,
                row.channel,
                row.target,
                row.alert_id,
                row.attempts,
                message_id or row.provider_message_id,
                exc,
            )
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
