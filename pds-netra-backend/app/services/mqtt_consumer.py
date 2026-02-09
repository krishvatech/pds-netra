"""
MQTT consumer for ingesting edge events into the backend.
"""

from __future__ import annotations

import json
import logging
import threading
import os
from typing import Optional

import paho.mqtt.client as mqtt

from ..core.config import settings
from ..core.db import SessionLocal
from ..core.errors import log_exception
from ..schemas.event import EventIn
from ..schemas.watchlist import FaceMatchEventIn
from ..schemas.presence import PresenceEventIn
from .event_ingest import handle_incoming_event
from .watchlist import ingest_face_match_event
from .presence import ingest_presence_event


class MQTTConsumer:
    """MQTT subscriber that ingests events into the database."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        protocol = os.getenv("MQTT_PROTOCOL", "v311").lower()
        if protocol == "v31":
            mqtt_protocol = mqtt.MQTTv31
        elif protocol == "v5":
            mqtt_protocol = mqtt.MQTTv5
        else:
            mqtt_protocol = mqtt.MQTTv311
        client_id = f"pds-netra-backend-{id(self)}"
        self.logger.info("MQTT client_id=%s protocol=%s", client_id, protocol)
        self.client = mqtt.Client(client_id=client_id, clean_session=True, protocol=mqtt_protocol)
        if settings.mqtt_username:
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        self.client.on_connect = self.on_connect  # type: ignore
        self.client.on_message = self.on_message  # type: ignore
        self.client.on_disconnect = self.on_disconnect  # type: ignore
        self.client.reconnect_delay_set(min_delay=1, max_delay=10)
        self._connected = threading.Event()

    def on_connect(self, client: mqtt.Client, userdata, flags, rc) -> None:  # type: ignore
        if rc == 0:
            self.logger.info(
                "Connected to MQTT broker %s:%s",
                settings.mqtt_broker_host,
                settings.mqtt_broker_port,
            )
            client.subscribe("pds/+/events", qos=1)
            client.subscribe("pds/+/face-match", qos=1)
            client.subscribe("pds/+/presence", qos=1)
            self._connected.set()
        else:
            self.logger.error("Failed to connect to MQTT broker with code %s", rc)
            if rc == 7:
                self.logger.error(
                    "MQTT connection refused. Check broker at %s:%s",
                    settings.mqtt_broker_host,
                    settings.mqtt_broker_port,
                )

    def on_disconnect(self, client: mqtt.Client, userdata, rc) -> None:  # type: ignore
        self._connected.clear()
        self.logger.warning("MQTT disconnected with return code %s", rc)

    def on_message(self, client: mqtt.Client, userdata, msg) -> None:  # type: ignore
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception as exc:
            self.logger.warning(
                "Invalid event payload topic=%s payload_len=%s err=%s",
                getattr(msg, "topic", None),
                len(msg.payload) if getattr(msg, "payload", None) is not None else None,
                exc,
            )
            return
        if isinstance(payload, dict) and payload.get("event_type") == "FACE_MATCH":
            try:
                face_event = FaceMatchEventIn.model_validate(payload)
            except Exception as exc:
                self.logger.warning(
                    "Invalid face match payload topic=%s payload_len=%s err=%s",
                    getattr(msg, "topic", None),
                    len(msg.payload) if getattr(msg, "payload", None) is not None else None,
                    exc,
                )
                return
            with SessionLocal() as db:
                try:
                    ingest_face_match_event(db, face_event)
                except Exception as exc:
                    self.logger.exception("Failed to ingest face match event: %s", exc)
            return
        if isinstance(payload, dict) and payload.get("event_type") in {"PERSON_DETECTED", "VEHICLE_DETECTED", "ANPR_HIT"}:
            try:
                presence_event = PresenceEventIn.model_validate(payload)
            except Exception as exc:
                self.logger.warning(
                    "Invalid presence payload topic=%s payload_len=%s err=%s",
                    getattr(msg, "topic", None),
                    len(msg.payload) if getattr(msg, "payload", None) is not None else None,
                    exc,
                )
                return
            with SessionLocal() as db:
                try:
                    ingest_presence_event(db, presence_event)
                except Exception as exc:
                    self.logger.exception("Failed to ingest presence event: %s", exc)
            return
        try:
            event_in = EventIn.parse_obj(payload)
        except Exception as exc:
            self.logger.warning(
                "Invalid event payload topic=%s payload_len=%s err=%s",
                getattr(msg, "topic", None),
                len(msg.payload) if getattr(msg, "payload", None) is not None else None,
                exc,
            )
            return
        with SessionLocal() as db:
            try:
                handle_incoming_event(event_in, db)
            except Exception as exc:
                self.logger.exception("Failed to ingest event: %s", exc)

    def start(self) -> None:
        try:
            self.client.connect_async(
                settings.mqtt_broker_host,
                settings.mqtt_broker_port,
                keepalive=60,
            )
            self.client.loop_start()
        except Exception as exc:
            self.logger.error(
                "MQTT connection failed for %s:%s (%s)",
                settings.mqtt_broker_host,
                settings.mqtt_broker_port,
                exc,
            )

    def stop(self) -> None:
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception as exc:
            log_exception(self.logger, "MQTT shutdown failed", exc=exc)

    def is_connected(self) -> bool:
        return self._connected.is_set()
