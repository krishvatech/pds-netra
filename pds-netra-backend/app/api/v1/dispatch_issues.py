"""
API endpoints for dispatch issues.
"""

from __future__ import annotations

from datetime import timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.dispatch_issue import DispatchIssue
from ...schemas.dispatch_issue import (
    DispatchIssueCreate,
    DispatchIssueOut,
    DispatchIssueUpdate,
)
from ...core.pagination import clamp_page_size


router = APIRouter(prefix="/api/v1/dispatch-issues", tags=["dispatch-issues"])


def _ensure_utc(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.post("", response_model=DispatchIssueOut)
def create_dispatch_issue(
    payload: DispatchIssueCreate,
    db: Session = Depends(get_db),
) -> DispatchIssue:
    issue_time = _ensure_utc(payload.issue_time_utc)
    issue = DispatchIssue(
        godown_id=payload.godown_id,
        camera_id=payload.camera_id,
        zone_id=payload.zone_id,
        issue_time_utc=issue_time,
        status="OPEN",
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue


@router.get("", response_model=dict)
def list_dispatch_issues(
    godown_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    db: Session = Depends(get_db),
) -> dict:
    page_size = clamp_page_size(page_size)
    query = db.query(DispatchIssue)
    if godown_id:
        query = query.filter(DispatchIssue.godown_id == godown_id)
    if status:
        query = query.filter(DispatchIssue.status == status)
    total = query.count()
    issues = (
        query.order_by(DispatchIssue.issue_time_utc.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [DispatchIssueOut.model_validate(i).model_dump() for i in issues],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.put("/{issue_id}", response_model=DispatchIssueOut)
def update_dispatch_issue(
    issue_id: int,
    payload: DispatchIssueUpdate,
    db: Session = Depends(get_db),
) -> DispatchIssue:
    issue = db.query(DispatchIssue).filter(DispatchIssue.id == issue_id).first()
    if not issue:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Dispatch issue not found")

    if payload.godown_id is not None:
        issue.godown_id = payload.godown_id
    if payload.camera_id is not None:
        issue.camera_id = payload.camera_id
    if payload.zone_id is not None:
        issue.zone_id = payload.zone_id
    if payload.issue_time_utc is not None:
        issue.issue_time_utc = _ensure_utc(payload.issue_time_utc)
    if payload.status is not None:
        issue.status = payload.status

    db.commit()
    db.refresh(issue)
    return issue


@router.delete("/{issue_id}")
def delete_dispatch_issue(
    issue_id: int,
    db: Session = Depends(get_db),
) -> dict:
    issue = db.query(DispatchIssue).filter(DispatchIssue.id == issue_id).first()
    if not issue:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Dispatch issue not found")

    db.delete(issue)
    db.commit()
    return {"status": "success", "id": issue_id}
