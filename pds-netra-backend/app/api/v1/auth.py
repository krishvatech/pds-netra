"""
Authentication endpoints for PDS Netra backend (PoC).

This provides a minimal login endpoint that returns a demo token
and user profile for the dashboard to use.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(payload: LoginIn) -> dict:
    # PoC-only: accept any credentials and return a demo token
    return {
        "access_token": "demo-token",
        "token_type": "bearer",
        "user": {
            "username": payload.username,
            "name": payload.username.title(),
            "role": "STATE_ADMIN",
            "district": None,
            "godown_id": None,
        },
    }
