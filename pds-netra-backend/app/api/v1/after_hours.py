"""
After-hours policy administration APIs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.auth import require_roles
from ...models.after_hours_policy import AfterHoursPolicy as AfterHoursPolicyModel
from ...models.after_hours_policy_audit import AfterHoursPolicyAudit
from ...schemas.after_hours import AfterHoursPolicyOut, AfterHoursPolicyUpdate, AfterHoursPolicyAuditOut
from ...services.after_hours import default_policy
from ...core.pagination import clamp_page_size, clamp_limit


router = APIRouter(prefix="/api/v1/after-hours", tags=["after-hours"])


def _validate_time(value: str, field_name: str) -> None:
    try:
        datetime.strptime(value, "%H:%M")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} time format (HH:MM)") from exc


def _to_out(row: AfterHoursPolicyModel, source: str = "override") -> dict:
    payload = AfterHoursPolicyOut.model_validate(row).model_dump()
    payload["source"] = source
    return payload


def _policy_snapshot(row: AfterHoursPolicyModel | None, fallback: dict) -> dict:
    if row is None:
        return dict(fallback)
    return {
        "timezone": row.timezone,
        "day_start": row.day_start,
        "day_end": row.day_end,
        "presence_allowed": row.presence_allowed,
        "cooldown_seconds": row.cooldown_seconds,
        "enabled": row.enabled,
    }


@router.get("/policies")
def list_policies(
    godown_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN")),
) -> dict:
    page_size = clamp_page_size(page_size)
    q = db.query(AfterHoursPolicyModel)
    if godown_id:
        q = q.filter(AfterHoursPolicyModel.godown_id == godown_id)
    total = q.count()
    rows = (
        q.order_by(AfterHoursPolicyModel.godown_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_to_out(r, source="override") for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/policies/{godown_id}")
def get_policy(
    godown_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN")),
) -> dict:
    row = db.query(AfterHoursPolicyModel).filter(AfterHoursPolicyModel.godown_id == godown_id).first()
    if row:
        return _to_out(row, source="override")
    policy = default_policy()
    return AfterHoursPolicyOut(
        id=None,
        godown_id=godown_id,
        timezone=policy.timezone,
        day_start=policy.day_start,
        day_end=policy.day_end,
        presence_allowed=policy.presence_allowed,
        cooldown_seconds=policy.cooldown_seconds,
        enabled=policy.enabled,
        source="default",
    ).model_dump()


@router.put("/policies/{godown_id}")
def upsert_policy(
    godown_id: str,
    payload: AfterHoursPolicyUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN")),
) -> dict:
    data = payload.model_dump(exclude_unset=True)
    if "day_start" in data and data["day_start"]:
        _validate_time(data["day_start"], "day_start")
    if "day_end" in data and data["day_end"]:
        _validate_time(data["day_end"], "day_end")
    row = db.query(AfterHoursPolicyModel).filter(AfterHoursPolicyModel.godown_id == godown_id).first()
    defaults = default_policy()
    if row is None:
        row = AfterHoursPolicyModel(
            godown_id=godown_id,
            timezone=defaults.timezone,
            day_start=defaults.day_start,
            day_end=defaults.day_end,
            presence_allowed=defaults.presence_allowed,
            cooldown_seconds=defaults.cooldown_seconds,
            enabled=defaults.enabled,
        )
        db.add(row)
    defaults_snapshot = {
        "timezone": defaults.timezone,
        "day_start": defaults.day_start,
        "day_end": defaults.day_end,
        "presence_allowed": defaults.presence_allowed,
        "cooldown_seconds": defaults.cooldown_seconds,
        "enabled": defaults.enabled,
    }
    before_snapshot = _policy_snapshot(row if row.id else None, defaults_snapshot)
    for key, value in data.items():
        if key == "cooldown_seconds" and value is not None:
            try:
                value = max(1, int(value))
            except Exception:
                raise HTTPException(status_code=400, detail="cooldown_seconds must be an integer")
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    after_snapshot = _policy_snapshot(row, defaults_snapshot)
    changes = {}
    for key, before_val in before_snapshot.items():
        after_val = after_snapshot.get(key)
        if before_val != after_val:
            changes[key] = {"from": before_val, "to": after_val}
    if changes:
        actor = user.username or user.role
        audit = AfterHoursPolicyAudit(
            godown_id=godown_id,
            actor=actor,
            source="api",
            changes=changes,
            before=before_snapshot,
            after=after_snapshot,
        )
        db.add(audit)
        db.commit()
    return _to_out(row, source="override")


@router.get("/policies/{godown_id}/audit")
def list_policy_audit(
    godown_id: str,
    limit: int = Query(100, ge=1),
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN")),
) -> dict:
    limit = clamp_limit(limit)
    rows = (
        db.query(AfterHoursPolicyAudit)
        .filter(AfterHoursPolicyAudit.godown_id == godown_id)
        .order_by(AfterHoursPolicyAudit.created_at.desc())
        .limit(limit)
        .all()
    )
    return {"items": [AfterHoursPolicyAuditOut.model_validate(r).model_dump() for r in rows], "total": len(rows)}
