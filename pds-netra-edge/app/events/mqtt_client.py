"""
MQTT client wrapper for publishing events and health messages.

This module wraps the paho-mqtt client to provide easy publishing of
structured events and health heartbeats. It takes care of connecting to
the broker, handling reconnections and serialising Pydantic models to
JSON. QoS=1 is used to ensure messages are delivered at least once.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Optional

import paho.mqtt.client as mqtt

from ..models.event import EventModel, HealthModel
from ..schemas.watchlist import FaceMatchEvent
from ..schemas.presence import PresenceEvent
from ..config import Settings


class MQTTClient:
    """
    A wrapper around paho-mqtt providing high-level publish APIs.

    Parameters
    ----------
    settings: Settings
        Application settings containing MQTT connection parameters and godown ID.
    client_id: Optional[str]
        Client identifier for MQTT. If not provided, a default is generated.
    """

    def __init__(self, settings: Settings, client_id: Optional[str] = None) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.settings = settings
        self.client = mqtt.Client(client_id=client_id)
        if settings.mqtt_username:
            # Set username/password if provided
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        # Configure callbacks
        self.client.on_connect = self.on_connect  # type: ignore
        self.client.on_disconnect = self.on_disconnect  # type: ignore
        self._connected = threading.Event()
        self._stop_flag = threading.Event()

    def on_connect(self, client: mqtt.Client, userdata, flags, rc) -> None:  # type: ignore
        if rc == 0:
            self.logger.info("Connected to MQTT broker %s:%s", self.settings.mqtt_broker_host, self.settings.mqtt_broker_port)
            self._connected.set()
        else:
            self.logger.error("Failed to connect to MQTT broker with code %s", rc)

    def on_disconnect(self, client: mqtt.Client, userdata, rc) -> None:  # type: ignore
        self.logger.warning("MQTT disconnected with return code %s", rc)
        if rc == 7:
            self.logger.warning(
                "MQTT connection refused. Check that the broker is running at %s:%s",
                self.settings.mqtt_broker_host,
                self.settings.mqtt_broker_port,
            )
        self._connected.clear()
        # Attempt reconnection in background thread
        if not self._stop_flag.is_set():
            reconnect_thread = threading.Thread(target=self._reconnect, daemon=True)
            reconnect_thread.start()

    def _reconnect(self) -> None:
        while not self._stop_flag.is_set():
            try:
                self.logger.info("Attempting to reconnect to MQTT broker…")
                self.client.reconnect()
                return
            except Exception as exc:
                self.logger.error("MQTT reconnection failed: %s", exc)
                time.sleep(5)

    def connect(self) -> None:
        """Connect to the MQTT broker and start the network loop."""
        self.client.connect(self.settings.mqtt_broker_host, self.settings.mqtt_broker_port, keepalive=60)
        # Start network loop in background thread
        self.client.loop_start()
        # Wait until connected or timeout after 10 seconds
        if not self._connected.wait(timeout=10):
            self.logger.warning("MQTT connection timeout; continuing anyway")

    def publish_event(self, event: EventModel) -> None:
        """Publish an event message to the configured events topic."""
        topic = f"pds/{event.godown_id}/events"
        payload = event.json()
        self.logger.info(
            "Publishing event %s type=%s camera=%s track=%s",
            event.event_id,
            event.event_type,
            event.camera_id,
            event.track_id,
        )
        result = self.client.publish(topic, payload, qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            self.logger.error("Failed to publish event: %s", mqtt.error_string(result.rc))

    def publish_health(self, health: HealthModel) -> None:
        """Publish a health heartbeat message to the configured health topic."""
        topic = f"pds/{health.godown_id}/health"
        payload = health.json()
        result = self.client.publish(topic, payload, qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            self.logger.error("Failed to publish health: %s", mqtt.error_string(result.rc))

    def publish_face_match(self, event: FaceMatchEvent) -> None:
        """Publish a face match event to the watchlist topic."""
        topic = f"pds/{event.godown_id}/face-match"
        payload = event.model_dump_json()
        result = self.client.publish(topic, payload, qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            self.logger.error("Failed to publish face match: %s", mqtt.error_string(result.rc))

    def publish_presence(self, event: PresenceEvent) -> None:
        """Publish an after-hours presence event to the presence topic."""
        topic = f"pds/{event.godown_id}/presence"
        payload = event.model_dump_json()
        result = self.client.publish(topic, payload, qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            self.logger.error("Failed to publish presence: %s", mqtt.error_string(result.rc))

    def stop(self) -> None:
        """Stop the MQTT client and its network loop."""
        self._stop_flag.set()
        self.client.loop_stop()
        try:
            self.client.disconnect()
        except Exception:
            pass
