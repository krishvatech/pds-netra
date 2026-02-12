"""
Pydantic schemas for authorized user request/response validation.
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class AuthorizedUserCreate(BaseModel):
    """Schema for creating a new authorized user."""
    person_id: str = Field(..., max_length=64, description="Unique identifier for the person")
    name: str = Field(..., max_length=128, description="Full name of the person")
    role: str | None = Field(None, max_length=64, description="Role (e.g., staff, admin, security)")
    godown_id: str | None = Field(None, max_length=64, description="Associated godown ID")
    is_active: bool = Field(True, description="Whether the user is currently active")


class AuthorizedUserUpdate(BaseModel):
    """Schema for updating an existing authorized user."""
    name: str | None = Field(None, max_length=128)
    role: str | None = Field(None, max_length=64)
    godown_id: str | None = Field(None, max_length=64)
    is_active: bool | None = None


class AuthorizedUserResponse(BaseModel):
    """Schema for authorized user response."""
    person_id: str
    name: str
    role: str | None
    godown_id: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AuthorizedUserFaceIndexItem(BaseModel):
    """Compact face index payload for edge sync from backend DB."""
    person_id: str
    name: str
    role: str | None
    godown_id: str | None
    embedding: list[float]

    class Config:
        from_attributes = True
