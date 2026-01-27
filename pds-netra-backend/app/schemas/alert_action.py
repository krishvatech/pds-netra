"""
Pydantic schemas for alert actions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AlertActionCreate(BaseModel):
    action_type: str
    actor: Optional[str] = None
    note: Optional[str] = None


class AlertActionOut(BaseModel):
    id: int
    alert_id: int
    action_type: str
    actor: Optional[str] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
