"""
Health endpoints for PDS Netra backend.

Provides summary and per-godown camera health.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from ...core.db import get_db
from ...core.config import settings
from ...models.godown import Godown, Camera
from ...models.event import Event
from ...core.auth import UserContext, get_optional_user


router = APIRouter(prefix="/api/v1/health", tags=["health"])

HEALTH_EVENT_TYPES = {"CAMERA_OFFLINE", "CAMERA_TAMPERED", "LOW_LIGHT"}

ADMIN_ROLES = {"STATE_ADMIN", "HQ_ADMIN"}


def _is_admin(user: UserContext | None) -> bool:
    if not user or not user.role:
        return False
    return (user.role or "").upper() in ADMIN_ROLES


def _godown_ids_for_user(db: Session, user: UserContext | None) -> list[str] | None:
    if _is_admin(user):
        return None
    if not user or not user.user_id:
        return []
    rows = db.query(Godown.id).filter(Godown.created_by_user_id == user.user_id).all()
    return [row[0] for row in rows]


def _event_to_item(event: Event) -> dict:
    return {
        "id": event.id,
        "event_id": event.event_id_edge,
        "godown_id": event.godown_id,
        "camera_id": event.camera_id,
        "event_type": event.event_type,
        "severity": event.severity_raw,
        "timestamp_utc": event.timestamp_utc,
        "bbox": None,
        "track_id": event.track_id,
        "image_url": event.image_url,
        "clip_url": event.clip_url,
        "meta": event.meta or {},
    }


def _as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


@router.get("/summary")
def health_summary(
    request: Request,
    db: Session = Depends(get_db),
    godown_id: str | None = Query(None),
    user: UserContext | None = Depends(get_optional_user),
) -> dict:
    # Recent health-related events (last 24h)
    allowed_godowns = _godown_ids_for_user(db, user)
    if godown_id:
        if allowed_godowns is not None and godown_id not in allowed_godowns:
            raise HTTPException(status_code=403, detail="Forbidden")
        resolved_godown_ids = [godown_id]
    else:
        resolved_godown_ids = allowed_godowns
    since = datetime.utcnow() - timedelta(hours=24)
    q_recent = (
        db.query(Event)
        .filter(Event.event_type.in_(HEALTH_EVENT_TYPES), Event.timestamp_utc >= since)
        .order_by(Event.timestamp_utc.desc())
        .limit(20)
    )
    def _filter_by_godown(query):
        if resolved_godown_ids is None:
            return query
        if not resolved_godown_ids:
            return query.filter(Event.godown_id == "__forbidden__")
        return query.filter(Event.godown_id.in_(resolved_godown_ids))

    q_recent_base = (
        db.query(Event)
        .filter(Event.event_type.in_(HEALTH_EVENT_TYPES), Event.timestamp_utc >= since)
    )
    q_recent = _filter_by_godown(q_recent_base).order_by(Event.timestamp_utc.desc()).limit(20)
    recent_events = q_recent.all()

    # Count cameras offline in last 30 minutes
    offline_since = datetime.utcnow() - timedelta(minutes=30)
    q_offline_base = (
        db.query(Event.camera_id)
        .filter(
            Event.event_type == "CAMERA_OFFLINE",
            Event.timestamp_utc >= offline_since,
        )
    )
    q_offline = _filter_by_godown(q_offline_base).distinct()
    offline_events = q_offline.all()
    offline_cameras = len(offline_events)

    # Godowns with issues = any offline camera or recent health event
    q_issues_base = (
        db.query(func.count(func.distinct(Event.godown_id)))
        .filter(Event.event_type.in_(HEALTH_EVENT_TYPES), Event.timestamp_utc >= since)
    )
    q_issues = _filter_by_godown(q_issues_base)
    godowns_with_issues = q_issues.scalar() or 0

    # Recent camera status list
    recent_status: List[dict] = []
    # Latest health event per camera (best-effort)
    q_latest_base = (
        db.query(Event)
        .filter(Event.event_type.in_(HEALTH_EVENT_TYPES))
        .order_by(Event.timestamp_utc.desc())
    )
    q_latest = _filter_by_godown(q_latest_base).limit(50)
    latest_events = q_latest.all()
    seen = set()
    for ev in latest_events:
        key = (ev.godown_id, ev.camera_id)
        if key in seen:
            continue
        seen.add(key)
        ev_ts = _as_naive_utc(ev.timestamp_utc)
        online = not (ev.event_type == "CAMERA_OFFLINE" and ev_ts >= offline_since)
        recent_status.append(
            {
                "godown_id": ev.godown_id,
                "camera_id": ev.camera_id,
                "online": online,
                "last_frame_utc": None,
                "last_tamper_reason": ev.meta.get("reason") if ev.meta else None,
            }
        )

    mqtt_status = {"enabled": False, "connected": False}
    consumer = getattr(request.app.state, "mqtt_consumer", None)
    if consumer is not None:
        mqtt_status = {"enabled": True, "connected": consumer.is_connected()}

    return {
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "godowns_with_issues": godowns_with_issues,
        "cameras_offline": offline_cameras,
        "recent_health_events": [_event_to_item(e) for e in recent_events],
        "recent_camera_status": recent_status,
        "mqtt_consumer": mqtt_status,
    }


@router.get("/mqtt")
def mqtt_health(request: Request) -> dict:
    consumer = getattr(request.app.state, "mqtt_consumer", None)
    if consumer is None:
        return {"enabled": False, "connected": False, "host": settings.mqtt_broker_host, "port": settings.mqtt_broker_port}
    return {
        "enabled": True,
        "connected": consumer.is_connected(),
        "host": settings.mqtt_broker_host,
        "port": settings.mqtt_broker_port,
    }


@router.get("/godowns/{godown_id}")
def godown_health(godown_id: str, db: Session = Depends(get_db)) -> dict:
    godown = db.get(Godown, godown_id)
    if not godown:
        raise HTTPException(status_code=404, detail="Godown not found")
    cameras = (
        db.query(Camera)
        .filter(Camera.godown_id == godown_id)
        .order_by(Camera.id.asc())
        .all()
    )
    # Determine online status based on recent offline events
    offline_since = datetime.utcnow() - timedelta(minutes=30)
    offline_ids = {
        row[0]
        for row in (
            db.query(Event.camera_id)
            .filter(
                Event.godown_id == godown_id,
                Event.event_type == "CAMERA_OFFLINE",
                Event.timestamp_utc >= offline_since,
            )
            .distinct()
            .all()
        )
    }
    return {
        "godown_id": godown_id,
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "cameras": [
            {
                "camera_id": c.id,
                "online": c.id not in offline_ids,
                "last_frame_utc": None,
                "last_tamper_reason": None,
            }
            for c in cameras
        ],
    }
