"""
Lightweight auth helpers for PoC RBAC checks.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException, Depends


@dataclass
class UserContext:
    role: str
    username: Optional[str] = None
    district: Optional[str] = None
    godown_id: Optional[str] = None


def _auth_disabled() -> bool:
    return os.getenv("PDS_AUTH_DISABLED", "true").lower() in {"1", "true", "yes"}

def _expected_token() -> str:
    token = os.getenv("PDS_AUTH_TOKEN")
    if token:
        return token
    env = (os.getenv("PDS_ENV") or os.getenv("APP_ENV") or "dev").strip().lower()
    if env == "prod":
        return ""
    return "demo-token"

def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    if not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    return token or None


def get_current_user(
    authorization: Optional[str] = Header(None),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    x_user_godown: Optional[str] = Header(None, alias="X-User-Godown"),
    x_user_district: Optional[str] = Header(None, alias="X-User-District"),
    x_user_name: Optional[str] = Header(None, alias="X-User-Name"),
) -> UserContext:
    if _auth_disabled():
        return UserContext(
            role=(x_user_role or "STATE_ADMIN").upper(),
            username=x_user_name,
            district=x_user_district,
            godown_id=x_user_godown,
        )
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    expected = _expected_token()
    if not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid token")
    return UserContext(
        role=(x_user_role or "STATE_ADMIN").upper(),
        username=x_user_name,
        district=x_user_district,
        godown_id=x_user_godown,
    )


def get_optional_user(
    authorization: Optional[str] = Header(None),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    x_user_godown: Optional[str] = Header(None, alias="X-User-Godown"),
    x_user_district: Optional[str] = Header(None, alias="X-User-District"),
    x_user_name: Optional[str] = Header(None, alias="X-User-Name"),
) -> Optional[UserContext]:
    if _auth_disabled():
        return UserContext(
            role=(x_user_role or "STATE_ADMIN").upper(),
            username=x_user_name,
            district=x_user_district,
            godown_id=x_user_godown,
        )
    if not authorization:
        return None
    return get_current_user(
        authorization=authorization,
        x_user_role=x_user_role,
        x_user_godown=x_user_godown,
        x_user_district=x_user_district,
        x_user_name=x_user_name,
    )


def require_roles(*roles: str):
    def _dep(user: UserContext = Depends(get_current_user)):
        # PoC: single access level. Do not enforce role-based checks.
        return user

    return _dep
