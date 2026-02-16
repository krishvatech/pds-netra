"""
Watchlist management APIs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Union

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.auth import require_roles
from ...schemas.watchlist import (
    WatchlistPersonOut,
    WatchlistPersonUpdate,
    WatchlistEmbeddingsCreate,
    FaceMatchEventOut,
)
from ...services import watchlist as watchlist_service
from ...core.pagination import clamp_page_size
from ...core.request_limits import enforce_upload_limit, read_upload_bytes_sync


router = APIRouter(prefix="/api/v1/watchlist", tags=["watchlist"])


@router.get("/persons")
def list_persons(
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN", "USER")),
) -> dict:
    page_size = clamp_page_size(page_size)
    persons, total = watchlist_service.list_persons(db, status=status, query=q, page=page, page_size=page_size)
    return {
        "items": [WatchlistPersonOut.model_validate(p).model_dump() for p in persons],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/persons")
def create_person(
    name: str = Form(...),
    alias: Optional[str] = Form(None),
    reason: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    reference_images: Optional[Union[UploadFile, List[UploadFile]]] = File(None),
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN", "USER")),
    request=Depends(enforce_upload_limit),
) -> dict:
    person = watchlist_service.create_person(db, name=name, alias=alias, reason=reason, notes=notes)
    if reference_images:
        images_payload = []
        images_list = reference_images if isinstance(reference_images, list) else [reference_images]
        for img in images_list:
            data = read_upload_bytes_sync(img)
            images_payload.append((data, img.content_type, img.filename))
        watchlist_service.add_person_images(db, person=person, images=images_payload)
        db.refresh(person)
    return WatchlistPersonOut.model_validate(person).model_dump()


@router.get("/persons/{person_id}")
def get_person(
    person_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN", "USER")),
) -> dict:
    person = watchlist_service.get_person(db, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return WatchlistPersonOut.model_validate(person).model_dump()


@router.patch("/persons/{person_id}")
def update_person(
    person_id: str,
    payload: WatchlistPersonUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN", "USER")),
) -> dict:
    person = watchlist_service.get_person(db, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    person = watchlist_service.update_person(db, person, payload.model_dump(exclude_unset=True))
    return WatchlistPersonOut.model_validate(person).model_dump()


@router.post("/persons/{person_id}/deactivate")
def deactivate_person(
    person_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN", "USER")),
) -> dict:
    person = watchlist_service.get_person(db, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    person = watchlist_service.deactivate_person(db, person)
    return WatchlistPersonOut.model_validate(person).model_dump()


@router.delete("/persons/{person_id}")
def delete_person(
    person_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN", "USER")),
) -> dict:
    person = watchlist_service.get_person(db, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    watchlist_service.delete_person(db, person)
    return {"status": "ok", "person_id": person_id}


@router.post("/persons/{person_id}/images")
def add_images(
    person_id: str,
    reference_images: Union[UploadFile, List[UploadFile]] = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN", "USER")),
    request=Depends(enforce_upload_limit),
) -> dict:
    person = watchlist_service.get_person(db, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    images_payload = []
    images_list = reference_images if isinstance(reference_images, list) else [reference_images]
    for img in images_list:
        data = read_upload_bytes_sync(img)
        images_payload.append((data, img.content_type, img.filename))
    watchlist_service.add_person_images(db, person=person, images=images_payload)
    db.refresh(person)
    return WatchlistPersonOut.model_validate(person).model_dump()


@router.post("/persons/{person_id}/embeddings")
def add_embeddings(
    person_id: str,
    payload: WatchlistEmbeddingsCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN", "USER")),
) -> dict:
    person = watchlist_service.get_person(db, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    watchlist_service.add_embeddings(db, person=person, embeddings=payload.embeddings)
    db.refresh(person)
    return WatchlistPersonOut.model_validate(person).model_dump()


@router.get("/persons/{person_id}/matches")
def list_matches(
    person_id: str,
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
    user=Depends(require_roles("STATE_ADMIN", "HQ_ADMIN", "USER")),
) -> dict:
    page_size = clamp_page_size(page_size)
    items, total = watchlist_service.list_person_matches(
        db,
        person_id=person_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [FaceMatchEventOut.model_validate(m).model_dump() for m in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/sync")
def sync_watchlist(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
) -> dict:
    page_size = clamp_page_size(page_size)
    payload = watchlist_service.build_sync_payload(db)
    items = payload.get("items") if isinstance(payload, dict) else None
    if isinstance(items, list):
        total = len(items)
        start = max((page - 1) * page_size, 0)
        end = start + page_size
        page_items = items[start:end]
        payload["items"] = page_items
        payload["total"] = total
        payload["page"] = page
        payload["page_size"] = page_size
        try:
            payload["checksum"] = watchlist_service._checksum_payload(page_items)  # type: ignore[attr-defined]
        except Exception:
            pass
    return payload
