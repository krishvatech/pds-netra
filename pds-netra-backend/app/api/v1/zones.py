"""
API endpoints for managing camera zones.
"""

from __future__ import annotations

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.auth import UserContext, get_current_user
from ...models.zone import Zone
from ...models.godown import Godown
from ...services.mqtt_publisher import publish_zones_config_changed
from ...schemas.zone import ZoneCreate, ZoneOut, ZoneUpdate
from ...core.pagination import clamp_page_size


router = APIRouter(prefix="/api/v1/zones", tags=["zones"])

ADMIN_ROLES = {"STATE_ADMIN", "HQ_ADMIN"}


def _is_admin(user: UserContext) -> bool:
    return (user.role or "").upper() in ADMIN_ROLES


def _zone_query_for_user(db: Session, user: UserContext):
    """Get zones that the user has access to."""
    query = db.query(Zone)
    if _is_admin(user):
        return query
    if not user.user_id:
        return query.filter(Zone.godown_id == "__forbidden__")
    # User can only see zones for godowns they created
    return (
        query.join(Godown, Godown.id == Zone.godown_id)
        .filter(Godown.created_by_user_id == user.user_id)
    )


def _get_zone_for_user(db: Session, zone_id: str, user: UserContext) -> Zone:
    zone = _zone_query_for_user(db, user).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return zone


def _can_access_godown(db: Session, user: UserContext, godown_id: str) -> bool:
    if _is_admin(user):
        return True
    if not user.user_id:
        return False
    godown = db.get(Godown, godown_id)
    return bool(godown and godown.created_by_user_id == user.user_id)


# List all zones for a camera or godown
@router.get("", response_model=dict)
def list_zones(
    godown_id: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    """List zones with optional filtering by godown, camera, or status."""
    page_size = clamp_page_size(page_size)
    query = _zone_query_for_user(db, user)

    if godown_id:
        query = query.filter(Zone.godown_id == godown_id)
    if camera_id:
        query = query.filter(Zone.camera_id == camera_id)
    if enabled is not None:
        query = query.filter(Zone.enabled == enabled)

    total = query.count()
    zones = (
        query.order_by(Zone.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": [ZoneOut.model_validate(z).model_dump() for z in zones],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# Get a single zone
@router.get("/{zone_id}", response_model=ZoneOut)
def get_zone(
    zone_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> ZoneOut:
    """Get a specific zone by ID."""
    zone = _get_zone_for_user(db, zone_id, user)
    return ZoneOut.model_validate(zone)


# Create a new zone
@router.post("", response_model=ZoneOut)
def create_zone(
    payload: ZoneCreate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> ZoneOut:
    """
    Create a new zone from UI coordinates.

    Example request:
    {
        "godown_id": "warehouse-1",
        "camera_id": "cam-001",
        "name": "Floor Area",
        "polygon": [[0.1, 0.2], [0.9, 0.2], [0.9, 0.8], [0.1, 0.8]],
        "pixels_per_meter": 120.0
    }
    """
    # Verify godown access
    if not _can_access_godown(db, user, payload.godown_id):
        raise HTTPException(status_code=403, detail="Cannot access this godown")

    # Validate godown exists
    godown = db.get(Godown, payload.godown_id)
    if not godown:
        raise HTTPException(status_code=404, detail="Godown not found")

    # Create zone with unique ID
    zone = Zone(
        id=str(uuid.uuid4()),
        godown_id=payload.godown_id,
        camera_id=payload.camera_id,
        name=payload.name,
        polygon=payload.polygon,
        pixels_per_meter=payload.pixels_per_meter,
        enabled=payload.enabled,
    )

    db.add(zone)
    db.commit()
    db.refresh(zone)

    publish_zones_config_changed(zone.godown_id, zone.camera_id)

    return ZoneOut.model_validate(zone)


# Update a zone
@router.put("/{zone_id}", response_model=ZoneOut)
def update_zone(
    zone_id: str,
    payload: ZoneUpdate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> ZoneOut:
    """Update an existing zone (e.g., redraw polygon)."""
    zone = _get_zone_for_user(db, zone_id, user)

    if payload.name is not None:
        zone.name = payload.name
    if payload.polygon is not None:
        zone.polygon = payload.polygon
    if payload.pixels_per_meter is not None:
        zone.pixels_per_meter = payload.pixels_per_meter
    if payload.enabled is not None:
        zone.enabled = payload.enabled

    db.add(zone)
    db.commit()
    db.refresh(zone)

    publish_zones_config_changed(zone.godown_id, zone.camera_id)

    return ZoneOut.model_validate(zone)


# Delete a zone
@router.delete("/{zone_id}", response_model=dict)
def delete_zone(
    zone_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    """Delete a zone and any associated rules."""
    zone = _get_zone_for_user(db, zone_id, user)

    godown_id = zone.godown_id
    camera_id = zone.camera_id
    db.delete(zone)
    db.commit()

    publish_zones_config_changed(godown_id, camera_id)

    return {"status": "deleted", "id": zone_id}
