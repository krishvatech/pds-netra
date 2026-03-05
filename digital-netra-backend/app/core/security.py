from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import bcrypt
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from app.core.config import settings


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(sub: str, user_id: str, is_admin: bool) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_exp_minutes)
    payload = {
        "sub": sub,
        "user_id": user_id,
        "is_admin": bool(is_admin),
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def validate_password_strength(password: str) -> List[str]:
    rules: List[str] = []
    if len(password) < 8:
        rules.append("min_length")
    if not any(ch.islower() for ch in password):
        rules.append("lowercase")
    if not any(ch.isupper() for ch in password):
        rules.append("uppercase")
    if not any(ch.isdigit() for ch in password):
        rules.append("digit")
    if not any(ch in "!@#$%^&*()-_=+[]{}|;:'\",.<>/?`~" for ch in password):
        rules.append("special")
    return rules


__all__ = [
    "ExpiredSignatureError",
    "InvalidTokenError",
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "validate_password_strength",
]
