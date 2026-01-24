"""
Pydantic schemas for dispatch issues in PDS Netra backend.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DispatchIssueCreate(BaseModel):
    godown_id: str
    camera_id: Optional[str] = None
    zone_id: Optional[str] = None
    issue_time_utc: datetime


class DispatchIssueOut(BaseModel):
    id: int
    godown_id: str
    camera_id: Optional[str]
    zone_id: Optional[str]
    issue_time_utc: datetime
    status: str
    started_at_utc: Optional[datetime]
    alerted_at_utc: Optional[datetime]
    alert_id: Optional[int]
    created_at_utc: datetime

    model_config = ConfigDict(from_attributes=True)
