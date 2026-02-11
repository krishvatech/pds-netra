"""
Authentication endpoints for PDS Netra backend (PoC).

This provides a minimal login endpoint that returns a demo token
and user profile for the dashboard to use.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...core.auth import UserContext, get_optional_user
from ...core.db import get_db
from ...core.security import create_access_token, hash_password, verify_password
from ...models.app_user import AppUser


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class RegisterIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=128)
    password: str = Field(..., min_length=6, max_length=256)
    role: str | None = Field(default=None, max_length=64)


ADMIN_ROLES = {"STATE_ADMIN", "HQ_ADMIN"}


def _auth_disabled() -> bool:
    return os.getenv("PDS_AUTH_DISABLED", "true").lower() in {"1", "true", "yes"}


def _build_login_response(
    *,
    username: str,
    role: str,
    user_id: str,
    token: str,
) -> dict:
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "username": username,
            "name": username.title(),
            "role": role,
            "district": None,
        },
    }


@router.post("/login")
def login(payload: LoginIn, db: Session = Depends(get_db)) -> dict:
    # PoC-only fallback mode.
    if _auth_disabled():
        token = "demo-token"
        role = "STATE_ADMIN"
        username = payload.username
        user_id = "demo"
    else:
        username = payload.username.strip()
        if not username or not payload.password:
            raise HTTPException(status_code=400, detail="username and password are required")
        user = db.query(AppUser).filter(func.lower(AppUser.username) == username.lower()).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        role = (user.role or "USER").upper()
        user_id = user.id
        token = create_access_token(sub=user.username, role=role, user_id=user_id)
    return _build_login_response(username=username, role=role, user_id=user_id, token=token)


@router.post("/register")
def register(
    payload: RegisterIn,
    db: Session = Depends(get_db),
    requester: UserContext | None = Depends(get_optional_user),
) -> dict:
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    if " " in username:
        raise HTTPException(status_code=400, detail="username cannot contain spaces")

    existing = db.query(AppUser).filter(func.lower(AppUser.username) == username.lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    total_users = db.query(func.count(AppUser.id)).scalar() or 0
    requested_role = (payload.role or "").strip().upper()
    role = requested_role or "USER"

    # Bootstrap: first registered account becomes admin.
    if total_users == 0:
        role = "STATE_ADMIN"
    elif role in ADMIN_ROLES:
        if not requester or requester.role.upper() not in ADMIN_ROLES:
            raise HTTPException(status_code=403, detail="Only admin can create admin users")

    user = AppUser(
        username=username,
        password_hash=hash_password(payload.password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = "demo-token" if _auth_disabled() else create_access_token(sub=user.username, role=role, user_id=user.id)
    return _build_login_response(username=user.username, role=role, user_id=user.id, token=token)
