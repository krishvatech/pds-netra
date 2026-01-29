"""
Schemas for alert reports.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AlertReportOut(BaseModel):
    id: str
    scope: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    summary_json: dict
    message_text: str
    email_html: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertReportListItem(BaseModel):
    id: str
    scope: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    created_at: datetime
    summary_json: dict

    model_config = ConfigDict(from_attributes=True)


class ReportGenerateRequest(BaseModel):
    period: Optional[str] = None  # 24h | 1h
