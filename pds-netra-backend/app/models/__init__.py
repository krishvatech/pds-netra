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
from .alert_action import AlertAction  # noqa: E402,F401
from .after_hours_policy import AfterHoursPolicy  # noqa: E402,F401
from .after_hours_policy_audit import AfterHoursPolicyAudit  # noqa: E402,F401
from .watchlist import WatchlistPerson, WatchlistPersonImage, WatchlistPersonEmbedding  # noqa: E402,F401
from .face_match_event import FaceMatchEvent  # noqa: E402,F401
from .notification_recipient import NotificationRecipient  # noqa: E402,F401
from .notification_endpoint import NotificationEndpoint  # noqa: E402,F401
from .notification_outbox import NotificationOutbox  # noqa: E402,F401
from .alert_report import AlertReport  # noqa: E402,F401
from .vehicle_gate_session import VehicleGateSession  # noqa: E402,F401
from .authorized_user import AuthorizedUser  # noqa: E402,F401
from .godown import Godown, Camera  # noqa: E402,F401
from .event import Event, Alert, AlertEventLink  # noqa: E402,F401
from .dispatch_issue import DispatchIssue  # noqa: E402,F401

__all__ = [
    "Base",

    # Rules / Policies
    "Rule",
    "AfterHoursPolicy",
    "AfterHoursPolicyAudit",

    # Alerts / Events
    "Alert",
    "Event",
    "AlertEventLink",
    "AlertAction",
    "AlertReport",

    # Watchlist / Face
    "WatchlistPerson",
    "WatchlistPersonImage",
    "WatchlistPersonEmbedding",
    "FaceMatchEvent",

    # Notifications
    "NotificationRecipient",
    "NotificationEndpoint",
    "NotificationOutbox",

    # Godown / Camera
    "Godown",
    "Camera",

    # Vehicle
    "VehicleGateSession",

    # Users / Dispatch
    "AuthorizedUser",
    "DispatchIssue",
]
