"""
Watchlist services for CRUD, sync payloads, and face match event ingestion.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Iterable, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.watchlist import WatchlistPerson, WatchlistPersonImage, WatchlistPersonEmbedding
from ..models.face_match_event import FaceMatchEvent
from ..models.event import Alert, Event, AlertEventLink
from ..schemas.watchlist import FaceMatchEventIn, WatchlistEmbeddingIn
from .storage import get_storage_provider
from .notifications import notify_blacklist_alert
from .mqtt_publisher import publish_watchlist_sync
from .incident_lifecycle import touch_detection_timestamp


def _utc_now() -> datetime:
    return datetime.utcnow()


def create_person(
    db: Session,
    *,
    name: str,
    alias: Optional[str] = None,
    reason: Optional[str] = None,
    notes: Optional[str] = None,
) -> WatchlistPerson:
    person = WatchlistPerson(
        name=name.strip(),
        alias=alias.strip() if alias else None,
        reason=reason.strip() if reason else None,
        notes=notes.strip() if notes else None,
        status="ACTIVE",
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    publish_watchlist_sync()
    return person


def update_person(db: Session, person: WatchlistPerson, updates: dict) -> WatchlistPerson:
    for key in ("name", "alias", "reason", "notes", "status"):
        if key in updates and updates[key] is not None:
            setattr(person, key, updates[key])
    db.add(person)
    db.commit()
    db.refresh(person)
    publish_watchlist_sync()
    return person


def deactivate_person(db: Session, person: WatchlistPerson) -> WatchlistPerson:
    person.status = "INACTIVE"
    db.add(person)
    db.commit()
    db.refresh(person)
    publish_watchlist_sync()
    return person


def add_person_images(
    db: Session,
    *,
    person: WatchlistPerson,
    images: Iterable[Tuple[bytes, Optional[str], Optional[str]]],
) -> list[WatchlistPersonImage]:
    """
    images: iterable of (bytes, content_type, filename_hint)
    """
    provider = get_storage_provider()
    saved: list[WatchlistPersonImage] = []
    for data, content_type, filename in images:
        result = provider.save_bytes(data=data, content_type=content_type, filename_hint=filename)
        img = WatchlistPersonImage(
            person_id=person.id,
            image_url=result.public_url,
            storage_path=result.storage_path,
        )
        db.add(img)
        saved.append(img)
    db.commit()
    for img in saved:
        db.refresh(img)
    publish_watchlist_sync()
    return saved


def add_embeddings(
    db: Session,
    *,
    person: WatchlistPerson,
    embeddings: list[WatchlistEmbeddingIn],
) -> list[WatchlistPersonEmbedding]:
    saved: list[WatchlistPersonEmbedding] = []
    for emb in embeddings:
        item = WatchlistPersonEmbedding(
            person_id=person.id,
            embedding=emb.embedding,
            embedding_version=emb.embedding_version,
            embedding_hash=emb.embedding_hash,
        )
        db.add(item)
        saved.append(item)
    db.commit()
    for item in saved:
        db.refresh(item)
    publish_watchlist_sync()
    return saved


def list_persons(
    db: Session,
    *,
    status: Optional[str] = None,
    query: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[WatchlistPerson], int]:
    q = db.query(WatchlistPerson)
    if status:
        q = q.filter(WatchlistPerson.status == status)
    if query:
        like = f"%{query.lower()}%"
        q = q.filter(
            func.lower(WatchlistPerson.name).like(like)
            | func.lower(WatchlistPerson.alias).like(like)
            | func.lower(WatchlistPerson.id).like(like)
        )
    total = q.count()
    items = (
        q.order_by(WatchlistPerson.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_person(db: Session, person_id: str) -> Optional[WatchlistPerson]:
    return db.get(WatchlistPerson, person_id)


def list_person_matches(
    db: Session,
    *,
    person_id: str,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[FaceMatchEvent], int]:
    q = db.query(FaceMatchEvent).filter(FaceMatchEvent.blacklist_person_id == person_id)
    if date_from:
        q = q.filter(FaceMatchEvent.occurred_at >= date_from)
    if date_to:
        q = q.filter(FaceMatchEvent.occurred_at <= date_to)
    total = q.count()
    items = (
        q.order_by(FaceMatchEvent.occurred_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def _checksum_payload(items: list[dict]) -> str:
    payload = json.dumps(items, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_sync_payload(db: Session) -> dict:
    persons = (
        db.query(WatchlistPerson)
        .filter(WatchlistPerson.status == "ACTIVE")
        .order_by(WatchlistPerson.updated_at.desc())
        .all()
    )
    items: list[dict] = []
    for person in persons:
        images = [
            {
                "id": img.id,
                "image_url": img.image_url,
                "storage_path": img.storage_path,
                "created_at": img.created_at,
            }
            for img in person.images
        ]
        embeddings = [
            {
                "embedding": emb.embedding,
                "embedding_version": emb.embedding_version,
                "embedding_hash": emb.embedding_hash,
            }
            for emb in person.embeddings
        ]
        items.append(
            {
                "id": person.id,
                "name": person.name,
                "alias": person.alias,
                "reason": person.reason,
                "status": person.status,
                "updated_at": person.updated_at,
                "images": images,
                "embeddings": embeddings,
            }
        )
    checksum = _checksum_payload(items)
    return {
        "schema_version": "1.0",
        "checksum": checksum,
        "generated_at": _utc_now(),
        "items": items,
    }


def ingest_face_match_event(db: Session, event_in: FaceMatchEventIn) -> Tuple[FaceMatchEvent, bool]:
    existing = db.get(FaceMatchEvent, event_in.event_id)
    if existing:
        return existing, False

    payload = event_in.payload
    person_candidate = payload.person_candidate
    evidence = payload.evidence

    face_event = FaceMatchEvent(
        id=event_in.event_id,
        occurred_at=event_in.occurred_at,
        godown_id=event_in.godown_id,
        camera_id=event_in.camera_id,
        stream_id=event_in.stream_id,
        match_score=person_candidate.match_score,
        is_blacklisted=person_candidate.is_blacklisted,
        blacklist_person_id=person_candidate.blacklist_person_id,
        snapshot_url=evidence.snapshot_url,
        storage_path=evidence.local_snapshot_path,
        correlation_id=event_in.correlation_id,
        raw_payload=event_in.model_dump(mode="json"),
    )
    db.add(face_event)
    db.commit()
    db.refresh(face_event)

    event_meta = {
        "person_id": person_candidate.blacklist_person_id,
        "match_score": person_candidate.match_score,
        "is_blacklisted": person_candidate.is_blacklisted,
        "correlation_id": event_in.correlation_id,
        "bbox": evidence.bbox,
    }
    person_name = None
    if person_candidate.blacklist_person_id:
        person = db.get(WatchlistPerson, person_candidate.blacklist_person_id)
        if person is not None:
            person_name = person.name
            event_meta["person_name"] = person.name
    event = Event(
        godown_id=event_in.godown_id,
        camera_id=event_in.camera_id,
        event_id_edge=event_in.event_id,
        event_type="FACE_MATCH",
        severity_raw="critical" if person_candidate.is_blacklisted else "info",
        timestamp_utc=event_in.occurred_at,
        bbox=str(evidence.bbox) if evidence.bbox else None,
        track_id=None,
        image_url=evidence.snapshot_url,
        clip_url=None,
        meta=event_meta,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    alert_created = False
    if person_candidate.is_blacklisted:
        alert, alert_created = _ensure_blacklist_alert(
            db,
            event=event,
            person_id=person_candidate.blacklist_person_id,
            person_name=person_name,
            match_score=person_candidate.match_score,
            snapshot_url=evidence.snapshot_url,
            correlation_id=event_in.correlation_id,
        )
        if alert_created:
            notify_blacklist_alert(db, alert, person_name=person_name, match_score=person_candidate.match_score, snapshot_url=evidence.snapshot_url)
    return face_event, alert_created


def _ensure_blacklist_alert(
    db: Session,
    *,
    event: Event,
    person_id: Optional[str],
    person_name: Optional[str],
    match_score: float,
    snapshot_url: Optional[str],
    correlation_id: Optional[str],
) -> Tuple[Alert, bool]:
    cutoff = event.timestamp_utc - timedelta(minutes=10)
    q = db.query(Alert).filter(
        Alert.godown_id == event.godown_id,
        Alert.alert_type == "BLACKLIST_PERSON_MATCH",
        Alert.start_time >= cutoff,
        Alert.status.in_(["OPEN", "ACK"]),
    )
    if person_id:
        candidates = None
        if db.bind and db.bind.dialect.name == "sqlite":
            candidates = q.all()
        else:
            try:
                existing = q.filter(Alert.extra["person_id"].astext == person_id).first()
                if existing:
                    candidates = None
                else:
                    candidates = []
            except Exception:
                candidates = q.all()
        if candidates is not None:
            existing = None
            for alert in candidates:
                extra = alert.extra or {}
                if extra.get("person_id") == person_id:
                    existing = alert
                    break
    else:
        existing = q.first()

    if existing:
        link = AlertEventLink(alert_id=existing.id, event_id=event.id)
        db.add(link)
        existing.end_time = event.timestamp_utc
        touch_detection_timestamp(existing, event.timestamp_utc)
        db.commit()
        return existing, False

    summary = "Blacklisted person detected"
    if person_name:
        summary = f"Blacklisted person detected: {person_name}"
    alert = Alert(
        godown_id=event.godown_id,
        camera_id=event.camera_id,
        alert_type="BLACKLIST_PERSON_MATCH",
        severity_final="critical",
        start_time=event.timestamp_utc,
        end_time=None,
        status="OPEN",
        title="Blacklisted Person Detected",
        summary=summary,
        zone_id=None,
        extra={
            "person_id": person_id,
            "person_name": person_name,
            "match_score": match_score,
            "snapshot_url": snapshot_url,
            "correlation_id": correlation_id,
        },
    )
    touch_detection_timestamp(alert, event.timestamp_utc)
    db.add(alert)
    db.flush()
    link = AlertEventLink(alert_id=alert.id, event_id=event.id)
    db.add(link)
    db.commit()
    db.refresh(alert)
    return alert, True
