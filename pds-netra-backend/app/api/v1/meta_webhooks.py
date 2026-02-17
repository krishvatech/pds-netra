"""
Public webhooks for Meta integrations (WhatsApp Cloud API).
"""

from __future__ import annotations

import datetime
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.notification_outbox import NotificationOutbox


logger = logging.getLogger("meta_webhooks")
router = APIRouter(prefix="/api/v1/meta", tags=["meta-webhooks"])


def _safe_status(status: Any) -> str:
    raw = str(status or "").strip().lower()
    if raw == "failed":
        return "FAILED"
    # We keep all successful provider lifecycle states under SENT for compatibility.
    if raw in {"sent", "delivered", "read"}:
        return "SENT"
    return "SENT"


def _status_error_text(item: dict[str, Any]) -> str | None:
    errors = item.get("errors")
    if not isinstance(errors, list) or not errors:
        return None
    parts: list[str] = []
    for err in errors:
        if not isinstance(err, dict):
            continue
        code = err.get("code")
        title = err.get("title") or err.get("message")
        detail = err.get("error_data", {}).get("details") if isinstance(err.get("error_data"), dict) else None
        chunk = f"code={code} title={title}" if code or title else None
        if chunk and detail:
            chunk = f"{chunk} detail={detail}"
        if chunk:
            parts.append(chunk)
    if not parts:
        return None
    return "Meta delivery failed: " + " | ".join(parts)


def _status_timestamp(item: dict[str, Any]) -> datetime.datetime | None:
    ts = item.get("timestamp")
    if ts is None:
        return None
    try:
        return datetime.datetime.fromtimestamp(int(str(ts)), tz=datetime.timezone.utc)
    except Exception:
        return None


@router.get("/webhook/whatsapp")
def verify_meta_whatsapp_webhook(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
) -> PlainTextResponse:
    expected = (os.getenv("META_WA_WEBHOOK_VERIFY_TOKEN") or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Webhook verify token not configured")
    if hub_mode != "subscribe" or not hub_verify_token or not hub_challenge:
        raise HTTPException(status_code=400, detail="Invalid webhook verify request")
    if hub_verify_token != expected:
        raise HTTPException(status_code=403, detail="Invalid verify token")
    return PlainTextResponse(content=hub_challenge)


@router.post("/webhook/whatsapp")
async def receive_meta_whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, int]:
    body = await request.json()
    updates = 0
    matched = 0

    entries = body.get("entry") if isinstance(body, dict) else None
    if not isinstance(entries, list):
        return {"updates": 0, "matched": 0}

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes")
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            statuses = value.get("statuses")
            if not isinstance(statuses, list):
                continue
            for item in statuses:
                if not isinstance(item, dict):
                    continue
                updates += 1
                wamid = str(item.get("id") or "").strip()
                if not wamid:
                    continue
                row = (
                    db.query(NotificationOutbox)
                    .filter(
                        NotificationOutbox.channel == "WHATSAPP",
                        NotificationOutbox.provider_message_id == wamid,
                    )
                    .first()
                )
                if not row:
                    logger.info("Meta status callback unmatched wamid=%s", wamid)
                    continue

                matched += 1
                provider_status = str(item.get("status") or "").strip().lower()
                row.status = _safe_status(provider_status)

                ts = _status_timestamp(item)
                if row.status == "SENT":
                    if ts:
                        row.sent_at = ts
                    elif row.sent_at is None:
                        row.sent_at = datetime.datetime.now(datetime.timezone.utc)
                    if provider_status in {"delivered", "read"}:
                        row.last_error = f"Meta delivery status: {provider_status}"
                    else:
                        row.last_error = None
                    row.next_retry_at = None
                else:
                    row.last_error = _status_error_text(item) or "Meta delivery failed"
                    row.next_retry_at = None

                db.add(row)

    if matched:
        db.commit()

    return {"updates": updates, "matched": matched}
