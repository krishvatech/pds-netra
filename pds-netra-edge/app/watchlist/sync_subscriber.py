"""
MQTT subscriber to trigger watchlist syncs on demand.
"""

from __future__ import annotations

import json
import logging
import threading

import paho.mqtt.client as mqtt

from ..config import Settings
from .manager import WatchlistManager


class WatchlistSyncSubscriber:
    def __init__(self, settings: Settings, manager: WatchlistManager) -> None:
        self.logger = logging.getLogger("WatchlistSyncSubscriber")
        self.settings = settings
        self.manager = manager
        self.client = mqtt.Client(client_id=f"pds-netra-watchlist-sub-{id(self)}")
        if settings.mqtt_username:
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        self.client.on_connect = self.on_connect  # type: ignore
        self.client.on_message = self.on_message  # type: ignore
        self._thread: threading.Thread | None = None

    def on_connect(self, client: mqtt.Client, userdata, flags, rc) -> None:  # type: ignore
        if rc == 0:
            client.subscribe("pds/watchlist/sync", qos=1)
            self.logger.info("Subscribed to watchlist sync")
        else:
            self.logger.warning("Watchlist sync MQTT connect failed: %s", rc)

    def on_message(self, client: mqtt.Client, userdata, msg) -> None:  # type: ignore
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            return
        if isinstance(payload, dict) and payload.get("event_type") == "WATCHLIST_SYNC":
            try:
                self.manager.sync_once()
            except Exception as exc:
                self.logger.warning("Watchlist sync trigger failed: %s", exc)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.client.connect_async(self.settings.mqtt_broker_host, self.settings.mqtt_broker_port, keepalive=30)
        self.client.loop_start()
        self._thread = threading.current_thread()

    def stop(self) -> None:
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass
