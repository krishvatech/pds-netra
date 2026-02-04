"""
Pydantic schemas for notification endpoints and delivery status.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, ConfigDict


class NotificationEndpointIn(BaseModel):
    scope: Literal["HQ", "GODOWN_MANAGER", "GODOWN"]
    godown_id: Optional[str] = None
    channel: Literal["WHATSAPP", "EMAIL", "CALL"]
    target: str
    is_enabled: bool = True


class NotificationEndpointUpdate(BaseModel):
    scope: Optional[Literal["HQ", "GODOWN_MANAGER", "GODOWN"]] = None
    godown_id: Optional[str] = None
    channel: Optional[Literal["WHATSAPP", "EMAIL", "CALL"]] = None
    target: Optional[str] = None
    is_enabled: Optional[bool] = None


class NotificationEndpointOut(BaseModel):
    id: str
    scope: str
    godown_id: Optional[str] = None
    channel: str
    target: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationDeliveryOut(BaseModel):
    id: str
    channel: str
    target: str
    status: str
    attempts: int
    next_retry_at: Optional[datetime] = None
    last_error: Optional[str] = None
    provider_message_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
