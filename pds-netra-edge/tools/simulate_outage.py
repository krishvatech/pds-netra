#!/usr/bin/env python3
"""
Simulate an MQTT outage and verify outbox buffering + replay.

Usage:
  python pds-netra-edge/tools/simulate_outage.py --config pds-netra-edge/config/pds_netra_config.yaml
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
import time
import uuid

from app.config import load_settings
from app.events.mqtt_client import MQTTClient
from app.schemas.presence import PresenceEvent, PresencePayload


def _utc_iso() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _make_presence_event(godown_id: str, camera_id: str) -> PresenceEvent:
    return PresenceEvent(
        event_id=str(uuid.uuid4()),
        occurred_at=_utc_iso(),
        timezone="UTC",
        godown_id=godown_id,
        camera_id=camera_id,
        event_type="PERSON_DETECTED",
        payload=PresencePayload(
            count=1,
            bbox=None,
            confidence=0.9,
            is_after_hours=False,
            evidence=None,
        ),
        correlation_id=str(uuid.uuid4()),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate MQTT outage + outbox replay")
    parser.add_argument(
        "--config",
        default="config/pds_netra_config.yaml",
        help="Path to edge YAML config",
    )
    parser.add_argument("--events", type=int, default=25, help="Number of events to emit")
    parser.add_argument(
        "--offline-host",
        default="127.0.0.1",
        help="MQTT host to use during outage phase",
    )
    parser.add_argument(
        "--offline-port",
        type=int,
        default=1884,
        help="MQTT port to use during outage phase",
    )
    parser.add_argument(
        "--online-host",
        default=None,
        help="MQTT host to use during replay phase (defaults to env MQTT_BROKER_HOST or localhost)",
    )
    parser.add_argument(
        "--online-port",
        type=int,
        default=None,
        help="MQTT port to use during replay phase (defaults to env MQTT_BROKER_PORT or 1883)",
    )
    parser.add_argument(
        "--flush-timeout-sec",
        type=int,
        default=20,
        help="How long to attempt replay before giving up",
    )
    parser.add_argument(
        "--skip-replay",
        action="store_true",
        help="Only enqueue events, skip replay attempt",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    os.environ["MQTT_BROKER_HOST"] = args.offline_host
    os.environ["MQTT_BROKER_PORT"] = str(args.offline_port)

    settings = load_settings(args.config)
    client = MQTTClient(settings)

    for idx in range(args.events):
        cam_id = f"SIM_CAM_{(idx % 2) + 1}"
        event = _make_presence_event(settings.godown_id, cam_id)
        client.publish_presence(event, http_fallback=False)

    if not client.outbox:
        print("Outbox is disabled; set EDGE_OUTBOX_ENABLED=true", file=sys.stderr)
        return 2

    stats = client.outbox.stats()
    print(f"Outbox after enqueue: pending={stats.get('pending', 0)} sent={stats.get('sent', 0)} dead={stats.get('dead', 0)}")

    if args.skip_replay:
        client.stop()
        return 0

    online_host = args.online_host or os.getenv("MQTT_BROKER_HOST", "localhost")
    online_port = args.online_port or int(os.getenv("MQTT_BROKER_PORT", "1883"))
    os.environ["MQTT_BROKER_HOST"] = str(online_host)
    os.environ["MQTT_BROKER_PORT"] = str(online_port)

    settings = load_settings(args.config)
    client_replay = MQTTClient(settings)
    client_replay.connect()
    client_replay.start_outbox()

    deadline = time.time() + max(5, args.flush_timeout_sec)
    while time.time() < deadline:
        stats = client_replay.outbox.stats()
        pending = stats.get("pending", 0)
        if pending == 0:
            break
        client_replay._flush_outbox_once()  # best-effort drain
        time.sleep(1)

    stats = client_replay.outbox.stats()
    print(
        "Outbox after replay: pending=%s sent=%s dead=%s"
        % (stats.get("pending", 0), stats.get("sent", 0), stats.get("dead", 0))
    )

    client_replay.stop()
    client.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
