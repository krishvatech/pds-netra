"""
ORM models for watchlist persons and their assets.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base


class WatchlistPerson(Base):
    __tablename__ = "watchlist_persons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(256))
    alias: Mapped[str | None] = mapped_column(String(256), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    images: Mapped[list[WatchlistPersonImage]] = relationship(
        "WatchlistPersonImage", back_populates="person", cascade="all, delete-orphan"
    )
    embeddings: Mapped[list[WatchlistPersonEmbedding]] = relationship(
        "WatchlistPersonEmbedding", back_populates="person", cascade="all, delete-orphan"
    )


class WatchlistPersonImage(Base):
    __tablename__ = "watchlist_person_images"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id: Mapped[str] = mapped_column(String(36), ForeignKey("watchlist_persons.id", ondelete="CASCADE"))
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    person: Mapped[WatchlistPerson] = relationship("WatchlistPerson", back_populates="images")


class WatchlistPersonEmbedding(Base):
    __tablename__ = "watchlist_person_embeddings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id: Mapped[str] = mapped_column(String(36), ForeignKey("watchlist_persons.id", ondelete="CASCADE"))
    embedding: Mapped[list[float]] = mapped_column(JSON)
    embedding_version: Mapped[str] = mapped_column(String(64), default="v1")
    embedding_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    person: Mapped[WatchlistPerson] = relationship("WatchlistPerson", back_populates="embeddings")
