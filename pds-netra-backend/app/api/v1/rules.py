"""
API endpoints for managing detection rules.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.db import get_db
import os
from ...models.rule import Rule
from ...models.godown import Godown
from ...models.anpr_vehicle import AnprVehicle
from ...services.rule_seed import seed_rules_for_godown
from ...schemas.rule import RuleCreate, RuleOut, RuleUpdate
from ...core.pagination import clamp_page_size
from ...core.auth import UserContext, get_current_user


router = APIRouter(prefix="/api/v1/rules", tags=["rules"])

ADMIN_ROLES = {"STATE_ADMIN", "HQ_ADMIN"}


def _is_admin(user: UserContext) -> bool:
    return (user.role or "").upper() in ADMIN_ROLES


def _rule_query_for_user(db: Session, user: UserContext):
    query = db.query(Rule)
    if _is_admin(user):
        return query
    if not user.user_id:
        return query.filter(Rule.godown_id == "__forbidden__")
    return query.join(Godown, Godown.id == Rule.godown_id).filter(Godown.created_by_user_id == user.user_id)


def _get_rule_for_user(db: Session, rule_id: int, user: UserContext) -> Rule:
    rule = _rule_query_for_user(db, user).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


def _can_access_godown_id(db: Session, user: UserContext, godown_id: str) -> bool:
    if _is_admin(user):
        return True
    if not user.user_id:
        return False
    godown = db.get(Godown, godown_id)
    return bool(godown and godown.created_by_user_id == user.user_id)

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
    "max_distance_m",
    "min_group_size",
    "pixels_per_meter",
    "allowed_plates",
    "blocked_plates",
    "zone_ids",
]


def _normalize_zone_ids(value: Any) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        items = [str(part).strip() for part in value]
    else:
        return None
    normalized: List[str] = []
    seen: set[str] = set()
    for item in items:
        if not item:
            continue
        if item not in seen:
            normalized.append(item)
            seen.add(item)
    return normalized or None


def _normalize_rule_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    zone_ids = _normalize_zone_ids(data.get("zone_ids"))
    if "zone_ids" in data:
        data["zone_ids"] = zone_ids

    rule_type = str(data.get("type") or "").strip().upper()
    zone_id = str(data.get("zone_id") or "").strip()

    if zone_ids:
        if len(zone_ids) == 1:
            data["zone_id"] = zone_ids[0]
        elif not zone_id or zone_id.lower() in {"all", "*", "__global__", "global"}:
            data["zone_id"] = "all"

    if rule_type == "WORKSTATION_ABSENCE":
        threshold = data.get("threshold_seconds")
        try:
            threshold_value = int(threshold) if threshold is not None else None
        except Exception:
            threshold_value = None
        if threshold_value is None or threshold_value < 1:
            raise HTTPException(status_code=422, detail="WORKSTATION_ABSENCE requires threshold_seconds >= 1")
        if not zone_ids and not zone_id:
            raise HTTPException(status_code=422, detail="WORKSTATION_ABSENCE requires one or more selected zones")
    return data


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
    user: UserContext = Depends(get_current_user),
) -> dict:
    page_size = clamp_page_size(page_size)
    query = _rule_query_for_user(db, user)
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
    user: UserContext = Depends(get_current_user),
) -> dict:
    page_size = clamp_page_size(page_size)
    query = _rule_query_for_user(db, user).filter(Rule.enabled == True)  # noqa: E712
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
    if (
        not rules
        and godown_id
        and os.getenv("AUTO_SEED_RULES", "true").lower() in {"1", "true", "yes"}
        and _can_access_godown_id(db, user, godown_id)
    ):
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
    user: UserContext = Depends(get_current_user),
) -> RuleOut:
    godown = db.get(Godown, payload.godown_id)
    if not godown:
        raise HTTPException(status_code=404, detail="Godown not found")
    if not _is_admin(user) and (not user.user_id or godown.created_by_user_id != user.user_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    data = _normalize_rule_payload(payload.model_dump())
    params = _extract_params(data)
    rule = Rule(
        godown_id=data["godown_id"],
        camera_id=data["camera_id"],
        zone_id=data["zone_id"],
        type=data["type"],
        enabled=data["enabled"],
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
    user: UserContext = Depends(get_current_user),
) -> RuleOut:
    rule = _get_rule_for_user(db, rule_id, user)
    data = _normalize_rule_payload(payload.model_dump(exclude_unset=True))
    if "godown_id" in data:
        godown = db.get(Godown, data["godown_id"])
        if not godown:
            raise HTTPException(status_code=404, detail="Godown not found")
        if not _is_admin(user) and (not user.user_id or godown.created_by_user_id != user.user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
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
    user: UserContext = Depends(get_current_user),
) -> dict:
    rule = _get_rule_for_user(db, rule_id, user)
    db.delete(rule)
    db.commit()
    return {"status": "deleted", "id": rule_id}
