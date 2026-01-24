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
from ...schemas.dispatch_issue import DispatchIssueCreate, DispatchIssueOut


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
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(DispatchIssue)
    if godown_id:
        query = query.filter(DispatchIssue.godown_id == godown_id)
    if status:
        query = query.filter(DispatchIssue.status == status)
    total = query.count()
    issues = query.order_by(DispatchIssue.issue_time_utc.desc()).all()
    return {"items": [DispatchIssueOut.model_validate(i).model_dump() for i in issues], "total": total}
