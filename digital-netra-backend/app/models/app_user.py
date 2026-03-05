from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.core.db import Base


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(sa.String(128), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(sa.String(255), unique=True, index=True, nullable=False)
    first_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    phone: Mapped[str | None] = mapped_column(sa.String(15), nullable=True)
    password_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()
    )
