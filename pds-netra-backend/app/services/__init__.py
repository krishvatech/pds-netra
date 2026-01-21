"""
Service layer for PDS Netra backend.

This package contains logic for ingesting events from the edge and applying
central rules to generate alerts.
"""

from .event_ingest import handle_incoming_event
from .rule_engine import apply_rules

__all__ = ["handle_incoming_event", "apply_rules"]