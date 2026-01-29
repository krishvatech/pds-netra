"""
Notification endpoints API.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.auth import require_roles
from ...models.notification_endpoint import NotificationEndpoint
from ...schemas.notifications import (
    NotificationEndpointIn,
    NotificationEndpointOut,
    NotificationEndpointUpdate,
)


router = APIRouter(prefix="/api/v1/notification", tags=["notification"])


@router.get("/endpoints", response_model=list[NotificationEndpointOut])
def list_endpoints(
    scope: str | None = Query(None),
    godown_id: str | None = Query(None),
    channel: str | None = Query(None),
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN")),
) -> list[NotificationEndpointOut]:
    query = db.query(NotificationEndpoint)
    if scope:
        scope_norm = scope.upper()
        if scope_norm == "GODOWN":
            scope_norm = "GODOWN_MANAGER"
        query = query.filter(NotificationEndpoint.scope == scope_norm)
    if godown_id:
        query = query.filter(NotificationEndpoint.godown_id == godown_id)
    if channel:
        query = query.filter(NotificationEndpoint.channel == channel.upper())
    return query.order_by(NotificationEndpoint.created_at.desc()).all()


@router.post("/endpoints", response_model=NotificationEndpointOut)
def create_endpoint(
    payload: NotificationEndpointIn,
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN")),
) -> NotificationEndpointOut:
    scope = payload.scope.upper()
    if scope == "GODOWN":
        scope = "GODOWN_MANAGER"
    if scope == "GODOWN_MANAGER" and not payload.godown_id:
        raise HTTPException(status_code=400, detail="godown_id is required for GODOWN_MANAGER scope")
    if scope == "HQ":
        godown_id = None
    else:
        godown_id = payload.godown_id
    endpoint = NotificationEndpoint(
        scope=scope,
        godown_id=godown_id,
        channel=payload.channel.upper(),
        target=payload.target,
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
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN")),
) -> NotificationEndpointOut:
    endpoint = db.get(NotificationEndpoint, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Notification endpoint not found")
    scope = endpoint.scope
    godown_id = endpoint.godown_id
    if payload.scope is not None:
        scope = payload.scope.upper()
        if scope == "GODOWN":
            scope = "GODOWN_MANAGER"
    if payload.godown_id is not None:
        godown_id = payload.godown_id
    if scope == "GODOWN_MANAGER" and not godown_id:
        raise HTTPException(status_code=400, detail="godown_id is required for GODOWN_MANAGER scope")
    if scope == "HQ":
        godown_id = None
    endpoint.scope = scope
    endpoint.godown_id = godown_id
    if payload.channel is not None:
        endpoint.channel = payload.channel.upper()
    if payload.target is not None:
        endpoint.target = payload.target
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
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN")),
) -> dict:
    endpoint = db.get(NotificationEndpoint, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Notification endpoint not found")
    db.delete(endpoint)
    db.commit()
    return {"status": "deleted", "id": endpoint_id}
