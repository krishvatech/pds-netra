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


class PasswordVerifyIn(BaseModel):
    password: str = Field(min_length=1)


class PasswordVerifyOut(BaseModel):
    valid: bool


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


class UserSessionOut(BaseModel):
    id: UUID
    email: EmailStr
    is_admin: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class AccountUpdateIn(BaseModel):
    first_name: str | None = Field(default=None, max_length=128)
    last_name: str | None = Field(default=None, max_length=128)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=15)
    password: str | None = None
    confirm_password: str | None = None

    @model_validator(mode="after")
    def validate_passwords_match(self) -> "AccountUpdateIn":
        if self.password or self.confirm_password:
            if not self.password or not self.confirm_password:
                raise ValueError("Both password fields are required")
            if self.password != self.confirm_password:
                raise ValueError("Passwords do not match")
        return self


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
