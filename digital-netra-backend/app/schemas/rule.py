from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RuleCreate(BaseModel):
    zone_id: UUID
    rule_name: str = Field(min_length=1, max_length=255)
    rule_type_id: UUID


class RuleUpdate(BaseModel):
    rule_name: str | None = Field(default=None, min_length=1, max_length=255)
    rule_type_id: UUID | None = None


class RuleOut(BaseModel):
    id: UUID
    zone_id: UUID
    rule_name: str
    rule_type_id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
