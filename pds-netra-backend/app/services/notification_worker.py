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


class MetaWhatsAppError(RuntimeError):
    def __init__(
        self,
        *,
        status_code: int,
        error_type: Optional[str],
        error_code: Optional[int],
        error_message: str,
        raw_detail: Optional[str] = None,
    ) -> None:
        self.status_code = status_code
        self.error_type = error_type
        self.error_code = error_code
        self.error_message = error_message
        self.raw_detail = raw_detail
        detail = f"type={error_type} code={error_code} message={error_message}"
        if raw_detail and raw_detail != detail:
            detail = f"{detail} raw={raw_detail}"
        super().__init__(f"Meta WhatsApp send failed status={status_code} detail={detail}")


class NotificationProvider:
    def send_whatsapp(
        self,
        to: str,
        message: str,
        media_url: Optional[str] = None,
        force_template: bool = False,
    ) -> Optional[str]:
        raise NotImplementedError

    def send_email(self, to: str, subject: str, html: str) -> Optional[str]:
        raise NotImplementedError

    def send_call(self, to: str, message: str) -> Optional[str]:
        raise NotImplementedError


class WhatsAppLogProvider(NotificationProvider):
    def send_whatsapp(
        self,
        to: str,
        message: str,
        media_url: Optional[str] = None,
        force_template: bool = False,
    ) -> Optional[str]:
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
        error_type: Optional[str] = None
        error_code: Optional[int] = None
        error_message: str = detail
        try:
            err_json = response.json()
            error_obj = err_json.get("error") if isinstance(err_json, dict) else None
            if isinstance(error_obj, dict):
                error_type = str(error_obj.get("type") or "") or None
                raw_code = error_obj.get("code")
                try:
                    error_code = int(raw_code) if raw_code is not None else None
                except Exception:
                    error_code = None
                error_message = str(error_obj.get("message") or detail)
        except Exception:
            pass
        raise MetaWhatsAppError(
            status_code=response.status_code,
            error_type=error_type,
            error_code=error_code,
            error_message=error_message,
            raw_detail=detail,
        )

    try:
        return response.json()
    except Exception as exc:
        raise RuntimeError(f"Meta WhatsApp send succeeded but response was not JSON: {exc}") from exc


class WhatsAppMetaProvider(NotificationProvider):
    def __init__(self) -> None:
        self.access_token = (os.getenv("META_WA_ACCESS_TOKEN") or "").strip()
        self.phone_number_id = (os.getenv("META_WA_PHONE_NUMBER_ID") or "").strip()
        self.api_version = (os.getenv("META_WA_API_VERSION") or "v20.0").strip() or "v20.0"
        self.template_name = (os.getenv("META_WA_TEMPLATE_NAME") or "").strip()
        self.template_language = (os.getenv("META_WA_TEMPLATE_LANGUAGE") or "en_US").strip() or "en_US"
        self.template_use_body_param = (
            (os.getenv("META_WA_TEMPLATE_USE_BODY_PARAM") or "false").strip().lower()
            in {"1", "true", "yes", "y"}
        )
        try:
            self.template_body_max_chars = max(1, int(os.getenv("META_WA_TEMPLATE_BODY_MAX_CHARS", "700")))
        except Exception:
            self.template_body_max_chars = 700
        try:
            self.template_body_param_count = max(0, int(os.getenv("META_WA_TEMPLATE_BODY_PARAM_COUNT", "0")))
        except Exception:
            self.template_body_param_count = 0
        configured_names = (os.getenv("META_WA_TEMPLATE_BODY_PARAM_NAMES") or "").strip()
        self.template_body_param_names = [part.strip() for part in configured_names.split(",") if part.strip()]
        missing = []
        if not self.access_token:
            missing.append("META_WA_ACCESS_TOKEN")
        if not self.phone_number_id:
            missing.append("META_WA_PHONE_NUMBER_ID")
        if missing:
            raise RuntimeError(f"Meta WhatsApp disabled (missing env): {', '.join(missing)}")

    def _extract_message_id(self, data: dict) -> Optional[str]:
        messages = data.get("messages") if isinstance(data, dict) else None
        if isinstance(messages, list) and messages:
            first = messages[0]
            if isinstance(first, dict):
                return first.get("id")
        return None

    def _send_payload(self, target: str, payload: dict) -> Optional[str]:
        data = _post_meta_whatsapp_message(
            access_token=self.access_token,
            api_version=self.api_version,
            phone_number_id=self.phone_number_id,
            payload=payload,
        )
        return self._extract_message_id(data)

    def _build_template_payload(self, target: str, message: str) -> dict:
        return self._build_template_payload_with_language(
            target,
            message,
            self.template_language,
            self.template_name,
        )

    def _default_template_param_count(self, template_name: str) -> int:
        if self.template_body_param_count > 0:
            return self.template_body_param_count
        if (template_name or "").strip().lower() == "object_alert":
            return 7
        return 1

    def _default_template_param_names(self, template_name: str, count: int) -> list[str]:
        defaults: list[str] = []
        if (template_name or "").strip().lower() == "object_alert" and count >= 7:
            defaults = [
                "event_type",
                "godown_name",
                "camera_name",
                "detection_time",
                "summary",
                "evidence_url",
                "ack_url",
            ][:count]
        if self.template_body_param_names:
            configured = self.template_body_param_names[:count]
            if len(configured) >= count or not defaults:
                return configured
            merged = list(configured)
            for name in defaults:
                if len(merged) >= count:
                    break
                if name not in merged:
                    merged.append(name)
            return merged[:count]
        return defaults

    def _parse_alert_message_fields(self, message: str) -> dict[str, str]:
        msg = (message or "").strip()
        lines = [ln.strip() for ln in msg.splitlines() if ln.strip()]
        fields: dict[str, str] = {
            "event_type": lines[0] if lines else "Alert",
            "godown_name": "-",
            "camera_name": "-",
            "detection_time": "-",
            "summary": "-",
            "evidence_url": "",
            "ack_url": "",
        }
        for ln in lines:
            lower = ln.lower()
            if lower.startswith("godown:"):
                fields["godown_name"] = ln.split(":", 1)[1].strip() or "-"
            elif lower.startswith("camera:"):
                fields["camera_name"] = ln.split(":", 1)[1].strip() or "-"
            elif lower.startswith("time:"):
                fields["detection_time"] = ln.split(":", 1)[1].strip() or "-"
            elif lower.startswith("details:"):
                fields["summary"] = ln.split(":", 1)[1].strip() or "-"
            elif lower.startswith("evidence:"):
                fields["evidence_url"] = ln.split(":", 1)[1].strip()
            elif lower.startswith("acknowledge:"):
                fields["ack_url"] = ln.split(":", 1)[1].strip()
        return fields

    def _build_template_text_params(
        self,
        message: str,
        count: int,
        template_name: str,
        *,
        include_param_names: bool = True,
    ) -> list[dict]:
        count = max(1, count)
        fields = self._parse_alert_message_fields(message)
        ordered = [
            fields["event_type"],
            fields["godown_name"],
            fields["camera_name"],
            fields["detection_time"],
            fields["summary"],
            fields["evidence_url"] or "-",
            fields["ack_url"] or "-",
        ]
        if count == 1:
            text = (message or "").strip()[: self.template_body_max_chars]
            return [{"type": "text", "text": text or "PDS Netra alert"}]

        param_names = self._default_template_param_names(template_name, count) if include_param_names else []
        params: list[dict] = []
        for i in range(count):
            if i < len(ordered):
                text = ordered[i]
            else:
                text = (message or "").strip()
            text = (text or "-")[: self.template_body_max_chars]
            entry = {"type": "text", "text": text}
            if i < len(param_names):
                entry["parameter_name"] = param_names[i]
            params.append(entry)
        return params

    def _expected_param_count_from_meta_error(self, exc: MetaWhatsAppError) -> Optional[int]:
        detail = (exc.raw_detail or "") + " " + (exc.error_message or "")
        match = re.search(r"expected number of params\s*\((\d+)\)", detail, flags=re.IGNORECASE)
        if not match:
            return None
        try:
            value = int(match.group(1))
            return value if value > 0 else None
        except Exception:
            return None

    def _build_template_payload_with_language(
        self,
        target: str,
        message: str,
        language_code: str,
        template_name: str,
        *,
        include_body_params: Optional[bool] = None,
        body_param_count: Optional[int] = None,
        include_param_names: bool = True,
    ) -> dict:
        template: dict = {
            "name": template_name,
            "language": {"code": language_code},
        }
        use_body = self.template_use_body_param if include_body_params is None else bool(include_body_params)
        if use_body and message:
            count = body_param_count if body_param_count is not None else self._default_template_param_count(template_name)
            template["components"] = [
                {
                    "type": "body",
                    "parameters": self._build_template_text_params(
                        message,
                        count,
                        template_name,
                        include_param_names=include_param_names,
                    ),
                }
            ]
        return {
            "messaging_product": "whatsapp",
            "to": target,
            "type": "template",
            "template": template,
        }

    def _template_name_candidates(self) -> list[str]:
        primary = (self.template_name or "").strip()
        configured = (os.getenv("META_WA_TEMPLATE_NAME_FALLBACKS") or "").strip()
        candidates: list[str] = []
        if primary:
            candidates.append(primary)
        if configured:
            candidates.extend([part.strip() for part in configured.split(",") if part.strip()])

        seen: set[str] = set()
        unique: list[str] = []
        for item in candidates:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def _template_language_candidates(self) -> list[str]:
        primary = (self.template_language or "").strip() or "en_US"
        configured = (os.getenv("META_WA_TEMPLATE_LANGUAGE_FALLBACKS") or "").strip()
        candidates: list[str] = [primary]
        if configured:
            # Respect explicit operator-provided order when configured.
            candidates.extend([part.strip() for part in configured.split(",") if part.strip()])
        else:
            lower_primary = primary.lower().replace("-", "_")
            if lower_primary == "en":
                candidates.append("en_US")
            elif lower_primary == "en_us":
                candidates.append("en")
            else:
                base = lower_primary.split("_", 1)[0]
                if base:
                    candidates.append(base)
                if base == "en":
                    candidates.append("en_US")

        seen: set[str] = set()
        unique: list[str] = []
        for item in candidates:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def _send_template_with_language_fallback(self, target: str, message: str) -> Optional[str]:
        last_exc: Optional[Exception] = None
        names = self._template_name_candidates()
        if not names:
            raise RuntimeError("Template fallback requested but META_WA_TEMPLATE_NAME is not configured")
        candidates = self._template_language_candidates()
        total_name = len(names)
        total_lang = len(candidates)
        for name_idx, template_name in enumerate(names):
            for lang_idx, lang in enumerate(candidates):
                try:
                    payload = self._build_template_payload_with_language(target, message, lang, template_name)
                    return self._send_payload(target, payload)
                except MetaWhatsAppError as exc:
                    has_next_combo = (name_idx < total_name - 1) or (lang_idx < total_lang - 1)
                    if exc.error_code == 132000:
                        expected_count = self._expected_param_count_from_meta_error(exc)
                        if expected_count:
                            last_retry_exc: Optional[MetaWhatsAppError] = None
                            for include_param_names in (False, True):
                                retry_payload = self._build_template_payload_with_language(
                                    target,
                                    message,
                                    lang,
                                    template_name,
                                    include_body_params=True,
                                    body_param_count=expected_count,
                                    include_param_names=include_param_names,
                                )
                                logger.warning(
                                    "Meta template params mismatch template=%s lang=%s; retrying with body_params=%s mode=%s",
                                    template_name,
                                    lang,
                                    expected_count,
                                    "named" if include_param_names else "positional",
                                )
                                try:
                                    return self._send_payload(target, retry_payload)
                                except MetaWhatsAppError as retry_exc:
                                    last_retry_exc = retry_exc
                                    detail = ((retry_exc.raw_detail or "") + " " + (retry_exc.error_message or "")).lower()
                                    if not include_param_names and (
                                        retry_exc.error_code == 132000
                                        or (retry_exc.error_code == 100 and "parameter name" in detail)
                                    ):
                                        logger.warning(
                                            "Meta template likely expects named params template=%s lang=%s; retrying with parameter_name fields",
                                            template_name,
                                            lang,
                                        )
                                        continue
                                    break
                            if last_retry_exc is not None:
                                retry_detail = (
                                    (last_retry_exc.raw_detail or "") + " " + (last_retry_exc.error_message or "")
                                ).lower()
                                if has_next_combo and (
                                    last_retry_exc.error_code in {132000, 132001}
                                    or (
                                        last_retry_exc.error_code == 100
                                        and "parameter name" in retry_detail
                                    )
                                ):
                                    logger.warning(
                                        "Meta template retry failed template=%s lang=%s err_code=%s; retrying next candidate",
                                        template_name,
                                        lang,
                                        last_retry_exc.error_code,
                                    )
                                    last_exc = last_retry_exc
                                    continue
                                raise last_retry_exc
                    # 132001 often means template name/translation mismatch for this WABA.
                    if exc.error_code == 132001 and has_next_combo:
                        logger.warning(
                            "Meta template lookup failed template=%s lang=%s; retrying next candidate",
                            template_name,
                            lang,
                        )
                        last_exc = exc
                        continue
                    raise
                except Exception as exc:
                    last_exc = exc
                    raise
        if last_exc is not None:
            raise last_exc
        return None

    def send_whatsapp(
        self,
        to: str,
        message: str,
        media_url: Optional[str] = None,
        force_template: bool = False,
    ) -> Optional[str]:
        target = _normalize_meta_whatsapp_target(to)
        msg = (message or "").strip() or "PDS Netra alert."
        if force_template:
            if not self.template_name:
                raise RuntimeError("Template fallback requested but META_WA_TEMPLATE_NAME is not configured")
            logger.info(
                "Meta WhatsApp force-template send to=%s template=%s lang=%s",
                target,
                self.template_name,
                self.template_language,
            )
            return self._send_template_with_language_fallback(target, msg)
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
            return self._send_payload(target, payload)
        except MetaWhatsAppError as exc:
            if exc.error_code == 131047 and self.template_name:
                logger.info(
                    "Meta WhatsApp session window closed for to=%s; retrying with template=%s lang=%s",
                    target,
                    self.template_name,
                    self.template_language,
                )
                return self._send_template_with_language_fallback(target, msg)
            logger.warning("Meta WhatsApp send failed to=%s err=%s", target, exc)
            raise
        except Exception as exc:
            logger.warning("Meta WhatsApp send failed to=%s err=%s", target, exc)
            raise

    def send_email(self, to: str, subject: str, html: str) -> Optional[str]:
        return None

    def send_call(self, to: str, message: str) -> Optional[str]:
        return None


class WhatsAppUnavailableProvider(NotificationProvider):
    def __init__(self, reason: str) -> None:
        self.reason = reason

    def send_whatsapp(
        self,
        to: str,
        message: str,
        media_url: Optional[str] = None,
        force_template: bool = False,
    ) -> Optional[str]:
        raise RuntimeError(self.reason)

    def send_email(self, to: str, subject: str, html: str) -> Optional[str]:
        return None

    def send_call(self, to: str, message: str) -> Optional[str]:
        return None

class EmailLogProvider(NotificationProvider):
    def send_whatsapp(
        self,
        to: str,
        message: str,
        media_url: Optional[str] = None,
        force_template: bool = False,
    ) -> Optional[str]:
        return None

    def send_email(self, to: str, subject: str, html: str) -> Optional[str]:
        logging.getLogger("notifications").info("Log Email to=%s subject=%s", to, subject)
        return None

    def send_call(self, to: str, message: str) -> Optional[str]:
        logging.getLogger("notifications").info("Log call to=%s message=%s", to, message)
        return None


class CallLogProvider(NotificationProvider):
    def send_whatsapp(
        self,
        to: str,
        message: str,
        media_url: Optional[str] = None,
        force_template: bool = False,
    ) -> Optional[str]:
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

    def send_whatsapp(
        self,
        to: str,
        message: str,
        media_url: Optional[str] = None,
        force_template: bool = False,
    ) -> Optional[str]:
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

    def send_whatsapp(
        self,
        to: str,
        message: str,
        media_url: Optional[str] = None,
        force_template: bool = False,
    ) -> Optional[str]:
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
            last_error = (outbox.last_error or "").lower()
            force_template = "retry_with_template=true" in last_error or "code=131047" in last_error
            try:
                return self.whatsapp.send_whatsapp(
                    outbox.target,
                    outbox.message,
                    media_url,
                    force_template=force_template,
                )
            except TypeError:
                # Backward compatibility for custom/mock providers in tests.
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
