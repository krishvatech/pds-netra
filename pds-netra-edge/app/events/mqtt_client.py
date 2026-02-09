"""
MQTT client wrapper for publishing events and health messages.

This module wraps the paho-mqtt client to provide easy publishing of
structured events and health heartbeats. It takes care of connecting to
the broker, handling reconnections and serialising Pydantic models to
JSON. QoS=1 is used to ensure messages are delivered at least once.
"""

from __future__ import annotations

import datetime
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

import paho.mqtt.client as mqtt

from ..models.event import EventModel, HealthModel
from ..schemas.watchlist import FaceMatchEvent
from ..schemas.presence import PresenceEvent
from ..config import Settings
from .confirm import ConfirmGate
from ..core.errors import log_exception
from .outbox import Outbox, load_outbox_settings, OutboxSettings


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
        self._confirm_gate = ConfirmGate()
        self._camera_states = None
        if settings.mqtt_username:
            # Set username/password if provided
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        # Configure callbacks
        self.client.on_connect = self.on_connect  # type: ignore
        self.client.on_disconnect = self.on_disconnect  # type: ignore
        self._connected = threading.Event()
        self._stop_flag = threading.Event()
        self._outbox_settings: OutboxSettings = load_outbox_settings()
        self.outbox: Optional[Outbox] = None
        self._outbox_thread: Optional[threading.Thread] = None
        self._outbox_stop = threading.Event()
        self._outbox_last_success: Optional[float] = None
        if self._outbox_settings.enabled:
            self.outbox = self._init_outbox(self._outbox_settings)

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

    def set_camera_states(self, camera_states) -> None:
        self._camera_states = camera_states

    def start_outbox(self) -> None:
        if not self.outbox:
            return
        if self._outbox_thread is not None and self._outbox_thread.is_alive():
            return
        self._outbox_thread = threading.Thread(target=self._outbox_loop, name="OutboxFlusher", daemon=True)
        self._outbox_thread.start()
        self.logger.info(
            "Outbox flusher started interval=%ss db=%s",
            self._outbox_settings.flush_interval_sec,
            self.outbox.db_path,
        )

    def publish_event(self, event: EventModel) -> None:
        """Publish an event message to the configured events topic."""
        rule_id = event.meta.rule_id if event.meta else event.event_type
        if not self._confirm_gate.push(
            camera_id=event.camera_id,
            rule_id=rule_id,
            now=time.time(),
            track_id=event.track_id,
        ):
            self.logger.debug(
                "Event dropped by confirm gate event=%s type=%s rule=%s track=%s",
                event.event_id,
                event.event_type,
                rule_id,
                event.track_id,
            )
            return
        topic = f"pds/{event.godown_id}/events"
        payload = self._serialize_payload(event)
        self.logger.info(
            "Publishing event %s type=%s camera=%s track=%s",
            event.event_id,
            event.event_type,
            event.camera_id,
            event.track_id,
        )
        self._publish_or_enqueue(
            topic=topic,
            payload=payload,
            event_type=event.event_type,
            camera_id=event.camera_id,
            godown_id=event.godown_id,
            http_fallback=False,
        )

    def publish_health(self, health: HealthModel) -> None:
        """Publish a health heartbeat message to the configured health topic."""
        topic = f"pds/{health.godown_id}/health"
        payload = self._serialize_payload(health)
        result = self.client.publish(topic, payload, qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            self.logger.error(
                "Failed to publish health rc=%s godown=%s",
                mqtt.error_string(result.rc),
                health.godown_id,
            )

    def publish_face_match(self, event: FaceMatchEvent, *, http_fallback: bool = False) -> None:
        """Publish a face match event to the watchlist topic."""
        topic = f"pds/{event.godown_id}/face-match"
        payload = self._serialize_payload(event)
        self._publish_or_enqueue(
            topic=topic,
            payload=payload,
            event_type=event.event_type,
            camera_id=event.camera_id,
            godown_id=event.godown_id,
            http_fallback=http_fallback,
        )

    def publish_presence(self, event: PresenceEvent, *, http_fallback: bool = False) -> None:
        """Publish an after-hours presence event to the presence topic."""
        topic = f"pds/{event.godown_id}/presence"
        payload = self._serialize_payload(event)
        self._publish_or_enqueue(
            topic=topic,
            payload=payload,
            event_type=event.event_type,
            camera_id=event.camera_id,
            godown_id=event.godown_id,
            http_fallback=http_fallback,
        )

    def stop(self) -> None:
        """Stop the MQTT client and its network loop."""
        self._stop_flag.set()
        self._outbox_stop.set()
        if self._outbox_thread is not None:
            self._outbox_thread.join(timeout=5)
        self.client.loop_stop()
        try:
            self.client.disconnect()
        except Exception as exc:
            log_exception(self.logger, "MQTT disconnect failed", exc=exc)
        if self.outbox is not None:
            self.outbox.close()

    def is_connected(self) -> bool:
        return self._connected.is_set()

    def _serialize_payload(self, event) -> str:
        if hasattr(event, "model_dump_json"):
            return event.model_dump_json()
        return event.json()

    def _publish_raw(self, topic: str, payload: str) -> bool:
        try:
            result = self.client.publish(topic, payload, qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                return True
            self.logger.warning(
                "MQTT publish failed rc=%s topic=%s",
                mqtt.error_string(result.rc),
                topic,
            )
            return False
        except Exception as exc:
            self.logger.warning("MQTT publish exception topic=%s error=%s", topic, exc)
            return False

    def _post_http_payload(self, payload_json: str) -> bool:
        import urllib.request

        backend_url = os.getenv("EDGE_BACKEND_URL", os.getenv("BACKEND_URL", "http://127.0.0.1:8001")).rstrip("/")
        url = f"{backend_url}/api/v1/edge/events"
        token = os.getenv("EDGE_BACKEND_TOKEN")
        if not token:
            self.logger.warning("HTTP fallback disabled (missing EDGE_BACKEND_TOKEN)")
            return False
        headers = {"Content-Type": "application/json"}
        headers["Authorization"] = f"Bearer {token}"
        headers["X-User-Role"] = "STATE_ADMIN"
        req = urllib.request.Request(url, data=payload_json.encode("utf-8"), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=3):
                return True
        except Exception as exc:
            self.logger.warning("HTTP event post failed: %s", exc)
            return False

    def _publish_or_enqueue(
        self,
        *,
        topic: str,
        payload: str,
        event_type: str,
        camera_id: Optional[str],
        godown_id: Optional[str],
        http_fallback: bool,
    ) -> None:
        published = False
        if self.is_connected():
            published = self._publish_raw(topic, payload)
        if published:
            self._record_event(camera_id)
            return

        if http_fallback and self._post_http_payload(payload):
            self._record_event(camera_id)
            self.logger.info(
                "HTTP fallback delivered event type=%s camera=%s",
                event_type,
                camera_id,
            )
            return

        if self.outbox:
            queued = self.outbox.enqueue(
                event_type=event_type,
                camera_id=camera_id,
                godown_id=godown_id,
                payload_json=payload,
                topic=topic,
                transport="mqtt",
                http_fallback=http_fallback,
            )
            if queued:
                self._record_event(camera_id)
                self.logger.warning(
                    "Event queued for retry type=%s camera=%s",
                    event_type,
                    camera_id,
                )
                return
        self.logger.error(
            "Event dropped (no outbox) type=%s camera=%s",
            event_type,
            camera_id,
        )

    def _record_event(self, camera_id: Optional[str]) -> None:
        if not camera_id or not self._camera_states:
            return
        state = self._camera_states.get(camera_id)
        if not state:
            return
        state.last_event_utc = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

    def _outbox_loop(self) -> None:
        last_summary = time.monotonic()
        while not self._outbox_stop.is_set():
            try:
                self._flush_outbox_once()
            except Exception as exc:
                log_exception(self.logger, "Outbox flush failed", exc=exc)
            now = time.monotonic()
            if now - last_summary >= self._outbox_settings.summary_interval_sec:
                stats = self.outbox.stats() if self.outbox else {}
                last_ok = None
                if self._outbox_last_success:
                    last_ok = int(time.time() - self._outbox_last_success)
                self.logger.info(
                    "Outbox summary pending=%s sent=%s dead=%s last_success_sec=%s",
                    stats.get("pending", 0),
                    stats.get("sent", 0),
                    stats.get("dead", 0),
                    last_ok,
                )
                last_summary = now
            self._outbox_stop.wait(timeout=self._outbox_settings.flush_interval_sec)

    def _flush_outbox_once(self) -> None:
        if not self.outbox:
            return
        rows = self.outbox.get_due(limit=100)
        for row in rows:
            ok = False
            err = ""
            if row.get("topic"):
                if self.is_connected():
                    ok = self._publish_raw(row["topic"], row["payload_json"])
                    if not ok:
                        err = "mqtt_publish_failed"
                else:
                    err = "mqtt_disconnected"
            else:
                err = "missing_topic"
            if not ok and row.get("http_fallback"):
                if self._post_http_payload(row["payload_json"]):
                    ok = True
                else:
                    err = f"{err};http_failed" if err else "http_failed"
            if ok:
                self.outbox.mark_sent(row["id"])
                self._outbox_last_success = time.time()
            else:
                self.outbox.mark_failed(
                    row["id"],
                    attempts=row.get("attempts", 0),
                    error=err,
                    max_attempts=self._outbox_settings.max_attempts,
                )

    def _init_outbox(self, settings: OutboxSettings) -> Optional[Outbox]:
        try:
            return Outbox(
                settings.db_path,
                max_queue=settings.max_queue,
                max_payload_bytes=settings.max_payload_bytes,
                logger=self.logger,
            )
        except Exception as exc:
            self.logger.error("Outbox init failed path=%s: %s", settings.db_path, exc)
        fallback = Path(__file__).resolve().parents[2] / "data" / "outbox.db"
        try:
            self.logger.warning("Outbox falling back to %s", fallback)
            return Outbox(
                fallback,
                max_queue=settings.max_queue,
                max_payload_bytes=settings.max_payload_bytes,
                logger=self.logger,
            )
        except Exception as exc:
            self.logger.error("Outbox fallback init failed path=%s: %s", fallback, exc)
            return None
