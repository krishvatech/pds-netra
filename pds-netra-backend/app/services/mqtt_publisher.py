"""
MQTT publisher utilities for backend-triggered notifications.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Optional

import paho.mqtt.client as mqtt

from ..core.config import settings


_logger = logging.getLogger("mqtt_publisher")

# Track the last config change time for the /api/v1/config/version endpoint
_last_config_change: datetime = datetime.utcnow()


def _publish_mqtt(topic: str, payload: dict) -> None:
    """Helper to publish MQTT message with common error handling."""
    try:
        client = mqtt.Client(client_id=f"pds-netra-{topic.replace('/', '-')}-{id(payload)}")
        if settings.mqtt_username:
            client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port, keepalive=30)
        client.publish(topic, json.dumps(payload), qos=1)
        client.disconnect()
    except Exception as exc:
        _logger.warning("Failed to publish MQTT on topic %s: %s", topic, exc)


def publish_watchlist_sync(godown_id: Optional[str] = None) -> None:
    if os.getenv("ENABLE_WATCHLIST_MQTT_SYNC", "true").lower() not in {"1", "true", "yes"}:
        return
    topic = "pds/watchlist/sync"
    payload = {
        "schema_version": "1.0",
        "event_type": "WATCHLIST_SYNC",
        "godown_id": godown_id,
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
    }
    _publish_mqtt(topic, payload)


def publish_camera_config_changed(godown_id: str, camera_id: str, action: str) -> None:
    """Publish config change event when a camera is created/updated/deleted."""
    global _last_config_change
    _last_config_change = datetime.utcnow()

    if os.getenv("ENABLE_CONFIG_MQTT_PUSH", "true").lower() not in {"1", "true", "yes"}:
        return

    topic = "pds/config/cameras"
    payload = {
        "schema_version": "1.0",
        "event_type": "CAMERA_CHANGED",
        "action": action,  # "created" | "updated" | "deleted"
        "godown_id": godown_id,
        "camera_id": camera_id,
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
    }
    _publish_mqtt(topic, payload)


def publish_rules_config_changed(godown_id: str, camera_id: str) -> None:
    """Publish config change event when any rule is created/updated/deleted."""
    global _last_config_change
    _last_config_change = datetime.utcnow()

    if os.getenv("ENABLE_CONFIG_MQTT_PUSH", "true").lower() not in {"1", "true", "yes"}:
        return

    topic = "pds/config/rules"
    payload = {
        "schema_version": "1.0",
        "event_type": "RULES_CHANGED",
        "godown_id": godown_id,
        "camera_id": camera_id,
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
    }
    _publish_mqtt(topic, payload)


def publish_zones_config_changed(godown_id: str, camera_id: str) -> None:
    """Publish config change event when any zone is created/updated/deleted."""
    global _last_config_change
    _last_config_change = datetime.utcnow()

    if os.getenv("ENABLE_CONFIG_MQTT_PUSH", "true").lower() not in {"1", "true", "yes"}:
        return

    topic = "pds/config/zones"
    payload = {
        "schema_version": "1.0",
        "event_type": "ZONES_CHANGED",
        "godown_id": godown_id,
        "camera_id": camera_id,
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
    }
    _publish_mqtt(topic, payload)


def get_last_config_change() -> datetime:
    """Get the timestamp of the last config change (for config version endpoint)."""
    return _last_config_change
