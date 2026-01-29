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
    try:
        client = mqtt.Client(client_id=f"pds-netra-watchlist-{id(payload)}")
        if settings.mqtt_username:
            client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port, keepalive=30)
        client.publish(topic, json.dumps(payload), qos=1)
        client.disconnect()
    except Exception as exc:
        _logger.warning("Failed to publish watchlist sync: %s", exc)
