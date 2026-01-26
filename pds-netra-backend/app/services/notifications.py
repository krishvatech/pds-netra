"""
Notification helpers for alerts (webhooks + email).
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
import urllib.request
from email.message import EmailMessage
from typing import Optional

from ..models.event import Alert, Event


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


def notify_alert(alert: Alert, event: Optional[Event] = None) -> None:
    payload = {
        "alert_id": alert.id,
        "alert_type": alert.alert_type,
        "severity": alert.severity_final,
        "status": alert.status,
        "godown_id": alert.godown_id,
        "camera_id": alert.camera_id,
        "zone_id": alert.zone_id,
        "summary": alert.summary,
        "start_time": alert.start_time.isoformat() if alert.start_time else None,
        "event_type": event.event_type if event else None,
        "event_id": event.event_id_edge if event else None,
    }
    _send_webhook(payload)
    _send_email(payload)
