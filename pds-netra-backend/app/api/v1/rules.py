"""
API endpoints for managing detection rules.
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.db import get_db
import os
from ...models.rule import Rule
from ...models.anpr_vehicle import AnprVehicle
from ...services.rule_seed import seed_rules_for_godown
from ...schemas.rule import RuleCreate, RuleOut, RuleUpdate
from ...core.pagination import clamp_page_size


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


def _active_anpr_vehicle_lists(db: Session, *, godown_id: str) -> tuple[list[str], list[str]]:
    rows = (
        db.query(AnprVehicle.plate_norm, AnprVehicle.list_type)
        .filter(
            AnprVehicle.godown_id == godown_id,
            AnprVehicle.is_active == True,  # noqa: E712
        )
        .all()
    )
    whitelist: set[str] = set()
    blacklist: set[str] = set()
    for plate_norm, list_type in rows:
        plate = (plate_norm or "").strip().upper()
        if not plate:
            continue
        lt = (list_type or "WHITELIST").strip().upper()
        if lt == "BLACKLIST":
            blacklist.add(plate)
        else:
            whitelist.add(plate)
    return sorted(whitelist), sorted(blacklist)


@router.get("", response_model=dict)
def list_rules(
    godown_id: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
) -> dict:
    page_size = clamp_page_size(page_size)
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
    items = (
        query.order_by(Rule.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_to_rule_out(r).model_dump() for r in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/active", response_model=dict)
def list_active_rules(
    godown_id: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
) -> dict:
    page_size = clamp_page_size(page_size)
    query = db.query(Rule).filter(Rule.enabled == True)  # noqa: E712
    if godown_id:
        query = query.filter(Rule.godown_id == godown_id)
    if camera_id:
        query = query.filter(Rule.camera_id == camera_id)
    total = query.count()
    rules = (
        query.order_by(Rule.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    if not rules and godown_id and os.getenv("AUTO_SEED_RULES", "true").lower() in {"1", "true", "yes"}:
        seed_rules_for_godown(db, godown_id)
        rules = (
            query.order_by(Rule.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

    items = [_to_active_payload(r) for r in rules]

    # Bridge ANPR "Vehicles" registry (WHITELIST/BLACKLIST) into edge-consumable rules.
    # Edge consumes /api/v1/rules/active and derives whitelist/blacklist plates from:
    # - ANPR_WHITELIST_ONLY.allowed_plates
    # - ANPR_BLACKLIST_ALERT.blocked_plates
    extra_items: list[dict] = []
    if godown_id:
        whitelist, blacklist = _active_anpr_vehicle_lists(db, godown_id=godown_id)
        if whitelist or blacklist:
            anpr_cameras = {r.camera_id for r in rules if str(r.type or "").strip().upper() == "ANPR_MONITOR"}
            if camera_id:
                anpr_cameras = {camera_id}

            for cam_id in sorted(anpr_cameras):
                if whitelist and not any(
                    it.get("camera_id") == cam_id and str(it.get("type") or "").upper() == "ANPR_WHITELIST_ONLY"
                    for it in items
                ):
                    extra_items.append(
                        {
                            "id": f"ANPR_WHITELIST_ONLY:{godown_id}:{cam_id}",
                            "type": "ANPR_WHITELIST_ONLY",
                            "camera_id": cam_id,
                            "zone_id": "all",
                            "allowed_plates": whitelist,
                        }
                    )
                if blacklist and not any(
                    it.get("camera_id") == cam_id and str(it.get("type") or "").upper() == "ANPR_BLACKLIST_ALERT"
                    for it in items
                ):
                    extra_items.append(
                        {
                            "id": f"ANPR_BLACKLIST_ALERT:{godown_id}:{cam_id}",
                            "type": "ANPR_BLACKLIST_ALERT",
                            "camera_id": cam_id,
                            "zone_id": "all",
                            "blocked_plates": blacklist,
                        }
                    )

    items.extend(extra_items)
    total = total + len(extra_items)
    if len(items) > page_size:
        items = items[:page_size]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


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
