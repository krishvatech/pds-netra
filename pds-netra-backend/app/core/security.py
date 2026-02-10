"""
Security helpers for password hashing and JWT access tokens.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty")
    salt = secrets.token_hex(16)
    rounds = int(os.getenv("PDS_PASSWORD_HASH_ROUNDS", "120000"))
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), rounds)
    return f"pbkdf2_sha256${rounds}${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, rounds_raw, salt, expected_hex = encoded.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        rounds = int(rounds_raw)
    except Exception:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), rounds)
    return secrets.compare_digest(digest.hex(), expected_hex)


def _jwt_secret() -> str:
    # Backward-compatible fallback to PDS_AUTH_TOKEN, but dedicated secret is preferred.
    secret = (os.getenv("PDS_JWT_SECRET") or os.getenv("PDS_AUTH_TOKEN") or "").strip()
    if secret:
        return secret
    env = (os.getenv("PDS_ENV") or os.getenv("APP_ENV") or "dev").strip().lower()
    if env == "prod":
        return ""
    return "dev-jwt-secret-change-me"


def _jwt_exp_minutes() -> int:
    try:
        return max(1, int(os.getenv("PDS_JWT_EXP_MIN", "720")))
    except Exception:
        return 720


def create_access_token(*, sub: str, role: str, user_id: str) -> str:
    secret = _jwt_secret()
    if not secret:
        raise RuntimeError("PDS_JWT_SECRET is required when auth is enabled")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "role": role,
        "user_id": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=_jwt_exp_minutes())).timestamp()),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = (
        f"{_b64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))}."
        f"{_b64url_encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))}"
    )
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any]:
    secret = _jwt_secret()
    if not secret:
        raise ValueError("JWT secret not configured")
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed token")
    header_b64, payload_b64, signature_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}"
    expected_sig = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    provided_sig = _b64url_decode(signature_b64)
    if not secrets.compare_digest(expected_sig, provided_sig):
        raise ValueError("Invalid signature")
    payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Invalid payload")
    exp = int(payload.get("exp") or 0)
    if exp <= 0:
        raise ValueError("Missing exp")
    now_ts = int(datetime.now(timezone.utc).timestamp())
    if now_ts >= exp:
        raise ValueError("Token expired")
    return payload
