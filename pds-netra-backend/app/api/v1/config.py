"""
Configuration version endpoint for detecting config changes.
"""

from __future__ import annotations

from fastapi import APIRouter

from ...services.mqtt_publisher import get_last_config_change


router = APIRouter(prefix="/api/v1/config", tags=["config"])


@router.get("/version", response_model=dict)
def get_config_version() -> dict:
    """
    Get the current configuration version.

    This lightweight endpoint allows edge nodes to detect config changes without MQTT.
    The version is updated whenever cameras, rules, or zones are created/updated/deleted.

    Example response:
    {
        "version": "2026-03-03T10:45:23.123456Z",
        "epoch_ms": 1740000000000
    }
    """
    last_change = get_last_config_change()
    # Format ISO string - isoformat() may already have Z or +00:00, so handle both
    iso_str = last_change.isoformat()
    if not iso_str.endswith('Z') and '+' not in iso_str:
        iso_str += "Z"
    epoch_ms = int(last_change.timestamp() * 1000)
    return {
        "version": iso_str,
        "epoch_ms": epoch_ms,
    }
