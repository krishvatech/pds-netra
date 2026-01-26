"""
API endpoints for managing detection rules.
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.rule import Rule
from ...schemas.rule import RuleCreate, RuleOut, RuleUpdate


router = APIRouter(prefix="/api/v1/rules", tags=["rules"])

PARAM_FIELDS = [
    "start_time",
    "end_time",
    "start",
    "end",
    "threshold_seconds",
    "start_local",
    "end_local",
    "cooldown_seconds",
    "require_active_dispatch_plan",
    "allowed_overage_percent",
    "threshold_distance",
    "allowed_plates",
    "blocked_plates",
]


def _extract_params(data: dict) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    for key in PARAM_FIELDS:
        if key in data and data[key] is not None:
            params[key] = data[key]
    return params


def _merge_params(rule: Rule, data: dict) -> None:
    params = dict(rule.params or {})
    for key in PARAM_FIELDS:
        if key in data:
            val = data[key]
            if val is None:
                params.pop(key, None)
            else:
                params[key] = val
    rule.params = params


def _to_rule_out(rule: Rule) -> RuleOut:
    payload = {
        "id": rule.id,
        "godown_id": rule.godown_id,
        "camera_id": rule.camera_id,
        "zone_id": rule.zone_id,
        "type": rule.type,
        "enabled": rule.enabled,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }
    params = rule.params or {}
    payload.update(params)
    return RuleOut.model_validate(payload)


def _to_active_payload(rule: Rule) -> dict:
    payload = {
        "id": str(rule.id),
        "type": rule.type,
        "camera_id": rule.camera_id,
        "zone_id": rule.zone_id,
    }
    params = rule.params or {}
    payload.update(params)
    return payload


@router.get("", response_model=dict)
def list_rules(
    godown_id: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Rule)
    if godown_id:
        query = query.filter(Rule.godown_id == godown_id)
    if camera_id:
        query = query.filter(Rule.camera_id == camera_id)
    if zone_id:
        query = query.filter(Rule.zone_id == zone_id)
    if type:
        query = query.filter(Rule.type == type)
    if enabled is not None:
        query = query.filter(Rule.enabled == enabled)
    total = query.count()
    items = query.order_by(Rule.id.desc()).all()
    return {"items": [_to_rule_out(r).model_dump() for r in items], "total": total}


@router.get("/active", response_model=dict)
def list_active_rules(
    godown_id: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Rule).filter(Rule.enabled == True)  # noqa: E712
    if godown_id:
        query = query.filter(Rule.godown_id == godown_id)
    if camera_id:
        query = query.filter(Rule.camera_id == camera_id)
    rules = query.order_by(Rule.id.asc()).all()
    return {"items": [_to_active_payload(r) for r in rules], "total": len(rules)}


@router.post("", response_model=RuleOut)
def create_rule(
    payload: RuleCreate,
    db: Session = Depends(get_db),
) -> RuleOut:
    data = payload.model_dump()
    params = _extract_params(data)
    rule = Rule(
        godown_id=payload.godown_id,
        camera_id=payload.camera_id,
        zone_id=payload.zone_id,
        type=payload.type,
        enabled=payload.enabled,
        params=params,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _to_rule_out(rule)


@router.put("/{rule_id}", response_model=RuleOut)
def update_rule(
    rule_id: int,
    payload: RuleUpdate,
    db: Session = Depends(get_db),
) -> RuleOut:
    rule = db.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    data = payload.model_dump(exclude_unset=True)
    if "godown_id" in data:
        rule.godown_id = data["godown_id"]
    if "camera_id" in data:
        rule.camera_id = data["camera_id"]
    if "zone_id" in data:
        rule.zone_id = data["zone_id"]
    if "type" in data:
        rule.type = data["type"]
    if "enabled" in data:
        rule.enabled = data["enabled"]
    _merge_params(rule, data)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _to_rule_out(rule)


@router.delete("/{rule_id}", response_model=dict)
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
) -> dict:
    rule = db.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return {"status": "deleted", "id": rule_id}
