from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserRuleTypeAssign(BaseModel):
    rule_type_ids: list[UUID] = Field(default_factory=list)


class UserRuleTypeOut(BaseModel):
    id: UUID
    user_id: UUID
    rule_type_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
