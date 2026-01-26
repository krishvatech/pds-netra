"""
SQLAlchemy model base class for PDS Netra backend.

This package defines ORM models for godowns, cameras, events, alerts, and
other entities used in the central backend. All models should inherit
from the declarative `Base` defined here.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


from .rule import Rule  # noqa: E402,F401

__all__ = ["Base", "Rule"]
