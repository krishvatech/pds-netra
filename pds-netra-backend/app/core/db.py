"""
Database session management for PDS Netra backend.

Uses SQLAlchemy 2.x style `Session` and declarative models. Provides a
session factory and dependency helper for use with FastAPI. A simple
context manager is provided to get a session in synchronous code.
"""

from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import settings


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


# Create SQLAlchemy engine
engine = create_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_size=_env_int("DB_POOL_SIZE", 5),
    max_overflow=_env_int("DB_MAX_OVERFLOW", 10),
    pool_recycle=_env_int("DB_POOL_RECYCLE_SEC", 1800),
    pool_timeout=_env_int("DB_POOL_TIMEOUT_SEC", 30),
)

# Create a configured session factory
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db():
    """Yield a database session for FastAPI dependencies."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SessionContext:
    """Context manager for database sessions outside of FastAPI."""

    def __enter__(self):
        self.db = SessionLocal()
        return self.db

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()
