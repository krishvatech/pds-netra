from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import ExpiredSignatureError, InvalidTokenError, decode_access_token
from app.models.app_user import AppUser
from app.models.rule_type import RuleType
from app.schemas.rule_type import RuleTypeCreate, RuleTypeOut, RuleTypeUpdate

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


def _normalize_payload(payload: RuleTypeCreate | RuleTypeUpdate) -> tuple[str, str, str]:
    name = payload.rule_type_name.strip()
    slug = payload.rule_type_slug.strip().lower()
    model_name = payload.model_name.strip()
    if not name or not slug or not model_name:
        raise HTTPException(status_code=400, detail="invalid_payload")
    return name, slug, model_name


def _get_rule_type_or_404(db: Session, rule_type_id: uuid.UUID) -> RuleType:
    rule_type = db.get(RuleType, rule_type_id)
    if not rule_type:
        raise HTTPException(status_code=404, detail="rule_type_not_found")
    return rule_type


@router.get("", response_model=list[RuleTypeOut])
def list_rule_types(request: Request, db: Session = Depends(get_db)):
    _get_admin_user(request, db)
    return db.execute(select(RuleType).order_by(RuleType.created_at.desc())).scalars().all()


@router.post("", response_model=RuleTypeOut, status_code=201)
def create_rule_type(payload: RuleTypeCreate, request: Request, db: Session = Depends(get_db)):
    _get_admin_user(request, db)
    name, slug, model_name = _normalize_payload(payload)

    existing_slug = db.execute(
        select(RuleType.id).where(func.lower(RuleType.rule_type_slug) == slug)
    ).scalars().first()
    if existing_slug:
        raise HTTPException(status_code=409, detail="rule_type_slug_taken")

    existing_name = db.execute(
        select(RuleType.id).where(func.lower(RuleType.rule_type_name) == name.lower())
    ).scalars().first()
    if existing_name:
        raise HTTPException(status_code=409, detail="rule_type_name_taken")

    rule_type = RuleType(rule_type_name=name, rule_type_slug=slug, model_name=model_name)
    db.add(rule_type)
    db.commit()
    db.refresh(rule_type)
    return rule_type


@router.put("/{rule_type_id}", response_model=RuleTypeOut)
def update_rule_type(
    rule_type_id: uuid.UUID, payload: RuleTypeUpdate, request: Request, db: Session = Depends(get_db)
):
    _get_admin_user(request, db)
    rule_type = _get_rule_type_or_404(db, rule_type_id)
    name, slug, model_name = _normalize_payload(payload)

    if slug != rule_type.rule_type_slug:
        existing_slug = db.execute(
            select(RuleType.id).where(
                func.lower(RuleType.rule_type_slug) == slug, RuleType.id != rule_type_id
            )
        ).scalars().first()
        if existing_slug:
            raise HTTPException(status_code=409, detail="rule_type_slug_taken")

    if name.lower() != rule_type.rule_type_name.lower():
        existing_name = db.execute(
            select(RuleType.id).where(
                func.lower(RuleType.rule_type_name) == name.lower(), RuleType.id != rule_type_id
            )
        ).scalars().first()
        if existing_name:
            raise HTTPException(status_code=409, detail="rule_type_name_taken")

    rule_type.rule_type_name = name
    rule_type.rule_type_slug = slug
    rule_type.model_name = model_name
    db.add(rule_type)
    db.commit()
    db.refresh(rule_type)
    return rule_type


@router.delete("/{rule_type_id}", status_code=204)
def delete_rule_type(rule_type_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    _get_admin_user(request, db)
    rule_type = _get_rule_type_or_404(db, rule_type_id)
    db.delete(rule_type)
    db.commit()
    return None
