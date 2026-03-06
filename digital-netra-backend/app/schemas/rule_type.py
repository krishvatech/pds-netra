from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RuleTypeCreate(BaseModel):
    rule_type_name: str = Field(min_length=1, max_length=128)
    rule_type_slug: str = Field(min_length=1, max_length=128)
    model_name: str = Field(min_length=1, max_length=128)


class RuleTypeUpdate(BaseModel):
    rule_type_name: str = Field(min_length=1, max_length=128)
    rule_type_slug: str = Field(min_length=1, max_length=128)
    model_name: str = Field(min_length=1, max_length=128)


class RuleTypeOut(BaseModel):
    id: UUID
    rule_type_name: str
    rule_type_slug: str
    model_name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
