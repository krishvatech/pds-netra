from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import ExpiredSignatureError, InvalidTokenError, decode_access_token
from app.models.app_user import AppUser
from app.models.rule_type import RuleType
from app.models.user_rule_type import UserRuleType
from app.schemas.user_rule_type import UserRuleTypeAssign, UserRuleTypeOut

router = APIRouter(redirect_slashes=False)
SESSION_COOKIE = "dn_session"


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return request.cookies.get(SESSION_COOKIE)


def _get_admin_user(request: Request, db: Session) -> AppUser:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="missing_token")
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token_expired")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid_token")

    raw_user_id = payload.get("user_id")
    if not raw_user_id:
        raise HTTPException(status_code=401, detail="invalid_token")
    try:
        user_id = uuid.UUID(str(raw_user_id))
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid_token")

    user = db.get(AppUser, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="user_not_found")
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="admin_only")
    return user


def _ensure_user_exists(db: Session, user_id: uuid.UUID) -> None:
    exists = db.execute(select(AppUser.id).where(AppUser.id == user_id)).scalars().first()
    if not exists:
        raise HTTPException(status_code=404, detail="user_not_found")


def _ensure_rule_types_exist(db: Session, rule_type_ids: set[uuid.UUID]) -> None:
    if not rule_type_ids:
        return
    found = set(
        db.execute(select(RuleType.id).where(RuleType.id.in_(rule_type_ids))).scalars().all()
    )
    missing = rule_type_ids - found
    if missing:
        raise HTTPException(status_code=404, detail="rule_type_not_found")


def _list_for_user(db: Session, user_id: uuid.UUID | None):
    query = select(UserRuleType).order_by(UserRuleType.created_at.desc())
    if user_id:
        query = query.where(UserRuleType.user_id == user_id)
    return db.execute(query).scalars().all()


@router.get("", response_model=list[UserRuleTypeOut])
def list_user_rule_types(
    request: Request,
    user_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    _get_admin_user(request, db)
    return _list_for_user(db, user_id)


@router.put("/{user_id}", response_model=list[UserRuleTypeOut])
def set_user_rule_types(
    user_id: uuid.UUID, payload: UserRuleTypeAssign, request: Request, db: Session = Depends(get_db)
):
    _get_admin_user(request, db)
    _ensure_user_exists(db, user_id)

    desired = set(payload.rule_type_ids)
    _ensure_rule_types_exist(db, desired)

    existing = db.execute(select(UserRuleType).where(UserRuleType.user_id == user_id)).scalars().all()
    existing_ids = {record.rule_type_id for record in existing}

    for record in existing:
        if record.rule_type_id not in desired:
            db.delete(record)

    for rule_type_id in desired - existing_ids:
        db.add(UserRuleType(user_id=user_id, rule_type_id=rule_type_id))

    db.commit()
    return _list_for_user(db, user_id)
