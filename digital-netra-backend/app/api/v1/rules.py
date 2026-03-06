from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import ExpiredSignatureError, InvalidTokenError, decode_access_token
from app.models.camera import Camera
from app.models.rule import Rule
from app.models.rule_type import RuleType
from app.models.user_rule_type import UserRuleType
from app.models.zone import Zone
from app.schemas.rule import RuleCreate, RuleOut, RuleUpdate

router = APIRouter(redirect_slashes=False)
SESSION_COOKIE = "dn_session"


def _get_user_context(request: Request) -> tuple[uuid.UUID, bool]:
    token = None
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
    if not token:
        token = request.cookies.get(SESSION_COOKIE)
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
    is_admin = bool(payload.get("is_admin", False))
    return user_id, is_admin


def _get_camera_or_404(db: Session, camera_id: uuid.UUID, user_id: uuid.UUID, is_admin: bool) -> Camera:
    query = select(Camera).where(Camera.id == camera_id)
    if not is_admin:
        query = query.where(Camera.user_id == user_id)
    camera = db.execute(query).scalars().first()
    if not camera:
        raise HTTPException(status_code=404, detail="camera_not_found")
    return camera


def _get_zone_or_404(db: Session, zone_id: uuid.UUID) -> Zone:
    zone = db.execute(select(Zone).where(Zone.id == zone_id)).scalars().first()
    if not zone:
        raise HTTPException(status_code=404, detail="zone_not_found")
    return zone


def _get_rule_or_404(db: Session, zone_id: uuid.UUID, rule_id: uuid.UUID) -> Rule:
    rule = (
        db.execute(select(Rule).where(Rule.id == rule_id, Rule.zone_id == zone_id)).scalars().first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="rule_not_found")
    return rule


def _ensure_rule_type_exists(db: Session, rule_type_id: uuid.UUID) -> None:
    exists = db.execute(select(RuleType.id).where(RuleType.id == rule_type_id)).scalars().first()
    if not exists:
        raise HTTPException(status_code=404, detail="rule_type_not_found")


def _ensure_rule_type_allowed(db: Session, user_id: uuid.UUID, is_admin: bool, rule_type_id: uuid.UUID) -> None:
    if is_admin:
        return
    allowed = (
        db.execute(
            select(UserRuleType.id).where(
                UserRuleType.user_id == user_id, UserRuleType.rule_type_id == rule_type_id
            )
        )
        .scalars()
        .first()
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="rule_type_forbidden")


@router.get("/zones/{zone_id}/rules", response_model=list[RuleOut])
def list_rules(zone_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    user_id, is_admin = _get_user_context(request)
    zone = _get_zone_or_404(db, zone_id)
    _get_camera_or_404(db, zone.camera_id, user_id, is_admin)
    return db.execute(select(Rule).where(Rule.zone_id == zone_id).order_by(Rule.created_at.desc())).scalars().all()


@router.post("/zones/{zone_id}/rules", response_model=RuleOut, status_code=201)
def create_rule(zone_id: uuid.UUID, payload: RuleCreate, request: Request, db: Session = Depends(get_db)):
    user_id, is_admin = _get_user_context(request)
    if payload.zone_id != zone_id:
        raise HTTPException(status_code=400, detail="zone_mismatch")

    zone = _get_zone_or_404(db, zone_id)
    _get_camera_or_404(db, zone.camera_id, user_id, is_admin)
    _ensure_rule_type_exists(db, payload.rule_type_id)
    _ensure_rule_type_allowed(db, user_id, is_admin, payload.rule_type_id)

    rule_name = payload.rule_name.strip()
    if not rule_name:
        raise HTTPException(status_code=400, detail="rule_name_required")

    rule = Rule(zone_id=zone_id, rule_name=rule_name, rule_type_id=payload.rule_type_id)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/zones/{zone_id}/rules/{rule_id}", response_model=RuleOut)
def get_rule(zone_id: uuid.UUID, rule_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    user_id, is_admin = _get_user_context(request)
    zone = _get_zone_or_404(db, zone_id)
    _get_camera_or_404(db, zone.camera_id, user_id, is_admin)
    return _get_rule_or_404(db, zone_id, rule_id)


@router.put("/zones/{zone_id}/rules/{rule_id}", response_model=RuleOut)
def update_rule(
    zone_id: uuid.UUID, rule_id: uuid.UUID, payload: RuleUpdate, request: Request, db: Session = Depends(get_db)
):
    user_id, is_admin = _get_user_context(request)
    zone = _get_zone_or_404(db, zone_id)
    _get_camera_or_404(db, zone.camera_id, user_id, is_admin)
    rule = _get_rule_or_404(db, zone_id, rule_id)

    if payload.rule_name is not None:
        rule_name = payload.rule_name.strip()
        if not rule_name:
            raise HTTPException(status_code=400, detail="rule_name_required")
        rule.rule_name = rule_name
    if payload.rule_type_id is not None:
        _ensure_rule_type_exists(db, payload.rule_type_id)
        _ensure_rule_type_allowed(db, user_id, is_admin, payload.rule_type_id)
        rule.rule_type_id = payload.rule_type_id

    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/zones/{zone_id}/rules/{rule_id}", status_code=204)
def delete_rule(zone_id: uuid.UUID, rule_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    user_id, is_admin = _get_user_context(request)
    zone = _get_zone_or_404(db, zone_id)
    _get_camera_or_404(db, zone.camera_id, user_id, is_admin)
    rule = _get_rule_or_404(db, zone_id, rule_id)
    db.delete(rule)
    db.commit()
    return None
