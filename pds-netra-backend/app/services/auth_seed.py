"""
Bootstrap seed helpers for app authentication users.
"""

from __future__ import annotations

import logging
import os

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.security import hash_password
from ..models.app_user import AppUser


def seed_admin_user(db: Session) -> None:
    logger = logging.getLogger("auth-seed")
    username = (os.getenv("PDS_ADMIN_USERNAME") or "admin").strip()
    password = (os.getenv("PDS_ADMIN_PASSWORD") or "").strip()
    role = (os.getenv("PDS_ADMIN_ROLE") or "STATE_ADMIN").strip().upper()

    if not username:
        logger.warning("Skipping admin seed: empty PDS_ADMIN_USERNAME")
        return
    if not password:
        logger.warning("Skipping admin seed: PDS_ADMIN_PASSWORD is empty")
        return

    existing = db.query(AppUser).filter(func.lower(AppUser.username) == username.lower()).first()
    if existing:
        changed = False
        if existing.role != role:
            existing.role = role
            changed = True
        if not existing.is_active:
            existing.is_active = True
            changed = True
        if changed:
            db.add(existing)
            db.commit()
        return

    db.add(
        AppUser(
            username=username,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
    )
    db.commit()
