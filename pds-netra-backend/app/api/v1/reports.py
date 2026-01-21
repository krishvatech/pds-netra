"""
Reporting endpoints for PDS Netra backend.

These endpoints produce aggregated summaries of events and alerts. For
demonstration purposes, only a simple count by alert_type is provided.
"""

from __future__ import annotations

from typing import List, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.event import Alert


router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/alerts/summary")
def alert_summary(
    godown_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, int]:
    """Return a simple count of open alerts by alert_type."""
    query = db.query(Alert)
    if godown_id:
        query = query.filter(Alert.godown_id == godown_id)
    query = query.filter(Alert.status == "OPEN")
    counts: Dict[str, int] = {}
    for alert in query:
        counts[alert.alert_type] = counts.get(alert.alert_type, 0) + 1
    return counts
