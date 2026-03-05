from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class SignupIn(BaseModel):
    username: str = Field(min_length=3, max_length=128)
    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=15)
    password: str = Field(min_length=8)
    confirm_password: str

    @model_validator(mode="after")
    def validate_passwords_match(self) -> "SignupIn":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    phone: str | None = None
    is_admin: bool
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UsernameCheckResponse(BaseModel):
    username: str
    available: bool


class EmailCheckResponse(BaseModel):
    email: EmailStr
    available: bool
