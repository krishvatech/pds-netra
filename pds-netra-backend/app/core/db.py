"""
Database session management for PDS Netra backend.

Uses SQLAlchemy 2.x style `Session` and declarative models. Provides a
session factory and dependency helper for use with FastAPI. A simple
context manager is provided to get a session in synchronous code.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import settings


# Create SQLAlchemy engine
engine = create_engine(settings.database_url, echo=False, future=True)

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
