"""
Notification endpoints API.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func

from ...core.db import get_db
from ...core.auth import require_roles
from ...models.notification_endpoint import NotificationEndpoint
from ...models.godown import Godown
from ...schemas.notifications import (
    NotificationEndpointIn,
    NotificationEndpointOut,
    NotificationEndpointUpdate,
)
from ...core.pagination import clamp_page_size, set_pagination_headers


router = APIRouter(prefix="/api/v1/notification", tags=["notification"])


def _is_admin(user) -> bool:
    return str(user.role).upper() in {"STATE_ADMIN", "HQ_ADMIN"}


def _owned_godown_ids(db: Session, user) -> set[str]:
    if not user.user_id:
        return set()
    rows = db.query(Godown.id).filter(Godown.created_by_user_id == user.user_id).all()
    return {row[0] for row in rows}


def _normalize_target(channel: str, target: str) -> str:
    value = (target or "").strip()
    channel_norm = (channel or "").upper()
    if channel_norm == "EMAIL":
        return value.lower()
    return value


def _endpoint_exists(
    db: Session,
    *,
    scope: str,
    godown_id: str | None,
    channel: str,
    target: str,
    exclude_id: str | None = None,
) -> bool:
    q = db.query(NotificationEndpoint).filter(
        NotificationEndpoint.scope == scope,
        NotificationEndpoint.godown_id == godown_id,
        NotificationEndpoint.channel == channel,
    )
    if channel == "EMAIL":
        q = q.filter(func.lower(NotificationEndpoint.target) == target.lower())
    else:
        q = q.filter(NotificationEndpoint.target == target)
    if exclude_id:
        q = q.filter(NotificationEndpoint.id != exclude_id)
    return db.query(q.exists()).scalar() is True


@router.get("/endpoints", response_model=list[NotificationEndpointOut])
def list_endpoints(
    response: Response,
    scope: str | None = Query(None),
    godown_id: str | None = Query(None),
    channel: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN", "GODOWN_MANAGER", "USER")),
) -> list[NotificationEndpointOut]:
    page_size = clamp_page_size(page_size)
    query = db.query(NotificationEndpoint)
    if not _is_admin(user):
        owned = _owned_godown_ids(db, user)
        if not owned:
            return []
        query = query.filter(
            NotificationEndpoint.scope == "GODOWN_MANAGER",
            NotificationEndpoint.godown_id.in_(owned),
        )
    else:
        if scope:
            scope_norm = scope.upper()
            if scope_norm == "GODOWN":
                scope_norm = "GODOWN_MANAGER"
            query = query.filter(NotificationEndpoint.scope == scope_norm)
        if godown_id:
            query = query.filter(NotificationEndpoint.godown_id == godown_id)
    if channel:
        query = query.filter(NotificationEndpoint.channel == channel.upper())
    total = query.count()
    items = (
        query.order_by(NotificationEndpoint.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    set_pagination_headers(response, total=total, page=page, page_size=page_size)
    return items


@router.post("/endpoints", response_model=NotificationEndpointOut)
def create_endpoint(
    payload: NotificationEndpointIn,
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN", "GODOWN_MANAGER", "USER")),
) -> NotificationEndpointOut:
    if _is_admin(user):
        scope = payload.scope.upper()
        if scope == "GODOWN":
            scope = "GODOWN_MANAGER"
        if scope == "GODOWN_MANAGER" and not payload.godown_id:
            raise HTTPException(status_code=400, detail="godown_id is required for GODOWN_MANAGER scope")
        if scope == "HQ":
            godown_id = None
        else:
            godown_id = payload.godown_id
    else:
        scope = "GODOWN_MANAGER"
        godown_id = (payload.godown_id or "").strip()
        if not godown_id:
            raise HTTPException(status_code=400, detail="godown_id is required")
        owned = _owned_godown_ids(db, user)
        if godown_id not in owned:
            raise HTTPException(status_code=403, detail="Forbidden")
    target_norm = _normalize_target(payload.channel, payload.target)
    if _endpoint_exists(
        db,
        scope=scope,
        godown_id=godown_id,
        channel=payload.channel.upper(),
        target=target_norm,
    ):
        raise HTTPException(status_code=409, detail="Notification endpoint already exists")
    endpoint = NotificationEndpoint(
        scope=scope,
        godown_id=godown_id,
        channel=payload.channel.upper(),
        target=target_norm,
        is_enabled=payload.is_enabled,
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return endpoint


@router.patch("/endpoints/{endpoint_id}", response_model=NotificationEndpointOut)
def update_endpoint(
    endpoint_id: str,
    payload: NotificationEndpointUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN", "GODOWN_MANAGER", "USER")),
) -> NotificationEndpointOut:
    endpoint = db.get(NotificationEndpoint, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Notification endpoint not found")
    if not _is_admin(user):
        owned = _owned_godown_ids(db, user)
        if endpoint.scope != "GODOWN_MANAGER" or endpoint.godown_id not in owned:
            raise HTTPException(status_code=403, detail="Forbidden")
    scope = endpoint.scope
    godown_id = endpoint.godown_id
    if payload.scope is not None:
        scope = payload.scope.upper()
        if scope == "GODOWN":
            scope = "GODOWN_MANAGER"
    if payload.godown_id is not None:
        godown_id = payload.godown_id
    if not _is_admin(user):
        owned = _owned_godown_ids(db, user)
        if scope == "HQ" or (godown_id and godown_id not in owned):
            raise HTTPException(status_code=403, detail="Forbidden")
        scope = "GODOWN_MANAGER"
        if not godown_id:
            raise HTTPException(status_code=400, detail="godown_id is required")
    if scope == "GODOWN_MANAGER" and not godown_id:
        raise HTTPException(status_code=400, detail="godown_id is required for GODOWN_MANAGER scope")
    if scope == "HQ":
        godown_id = None
    endpoint.scope = scope
    endpoint.godown_id = godown_id
    next_channel = endpoint.channel
    next_target = endpoint.target
    if payload.channel is not None:
        next_channel = payload.channel.upper()
    if payload.target is not None:
        next_target = _normalize_target(next_channel, payload.target)
    if _endpoint_exists(
        db,
        scope=scope,
        godown_id=godown_id,
        channel=next_channel,
        target=next_target,
        exclude_id=endpoint.id,
    ):
        raise HTTPException(status_code=409, detail="Notification endpoint already exists")
    endpoint.channel = next_channel
    endpoint.target = next_target
    if payload.is_enabled is not None:
        endpoint.is_enabled = payload.is_enabled
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return endpoint


@router.delete("/endpoints/{endpoint_id}")
def delete_endpoint(
    endpoint_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN", "GODOWN_MANAGER", "USER")),
) -> dict:
    endpoint = db.get(NotificationEndpoint, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Notification endpoint not found")
    if not _is_admin(user):
        owned = _owned_godown_ids(db, user)
        if endpoint.scope != "GODOWN_MANAGER" or endpoint.godown_id not in owned:
            raise HTTPException(status_code=403, detail="Forbidden")
    db.delete(endpoint)
    db.commit()
    return {"status": "deleted", "id": endpoint_id}
