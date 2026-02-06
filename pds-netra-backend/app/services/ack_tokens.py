"""
One-time acknowledgment token helpers.

We store only the sha256(token) in DB. The raw token is sent inside
WhatsApp/Email links and is never persisted.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Tuple


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def issue_ack_token(*, ttl_minutes: int) -> Tuple[str, str, datetime]:
    """
    Generate a new one-time token.

    Returns:
      raw_token: token to embed in links (do not store)
      token_hash: sha256(raw_token) to store in DB
      expires_at_utc: timezone-aware datetime (UTC)
    """
    raw = secrets.token_urlsafe(32)
    token_hash = sha256_hex(raw)
    expires = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    return raw, token_hash, expires


def verify_raw_token(raw_token: str, expected_hash: str | None) -> bool:
    if not raw_token or not expected_hash:
        return False
    return sha256_hex(raw_token) == expected_hash
