"""
Jetson smoke test: verify PERSON_LINE_CROSS events reach MQTT.

This script subscribes to edge events topic and waits for line-cross events
emitted by the running edge runtime.

Example:
  python3 pds-netra-edge/tools/smoke_person_line_cross_mqtt.py \
    --godown-id GDN_001 --camera-id CAM_GATE_1 --timeout 120
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from queue import Queue
from typing import Any, Dict


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test for PERSON_LINE_CROSS MQTT events")
    parser.add_argument("--godown-id", default=os.getenv("GODOWN_ID", "GDN_001"))
    parser.add_argument("--camera-id", default="", help="Optional camera filter")
    parser.add_argument("--broker-host", default=os.getenv("MQTT_BROKER_HOST", "127.0.0.1"))
    parser.add_argument("--broker-port", type=int, default=int(os.getenv("MQTT_BROKER_PORT", "1883")))
    parser.add_argument("--username", default=os.getenv("MQTT_USERNAME", ""))
    parser.add_argument("--password", default=os.getenv("MQTT_PASSWORD", ""))
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--expected-count", type=int, default=1)
    parser.add_argument("--topic", default="", help="Override topic; default pds/<godown_id>/events")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def _topic_for(godown_id: str, topic_override: str) -> str:
    if topic_override.strip():
        return topic_override.strip()
    return f"pds/{godown_id}/events"


def _is_match(payload: Dict[str, Any], godown_id: str, camera_id: str) -> bool:
    if payload.get("event_type") != "PERSON_LINE_CROSS":
        return False
    if payload.get("godown_id") != godown_id:
        return False
    if camera_id and payload.get("camera_id") != camera_id:
        return False
    return True


def _load_mqtt_module():
    try:
        import paho.mqtt.client as mqtt
    except Exception as exc:  # pragma: no cover
        print(
            f"[FAIL] Missing dependency paho-mqtt ({exc}). "
            "Install with: pip install paho-mqtt",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return mqtt


def main() -> int:
    args = _parse_args()
    topic = _topic_for(args.godown_id, args.topic)
    matches: "Queue[Dict[str, Any]]" = Queue()
    mqtt = _load_mqtt_module()

    client = mqtt.Client(client_id=f"smoke-person-line-{int(time.time())}", clean_session=True)
    if args.username:
        client.username_pw_set(args.username, args.password or None)

    def on_connect(cli, userdata, flags, rc):  # type: ignore[no-untyped-def]
        _ = userdata
        _ = flags
        if rc != 0:
            print(f"[FAIL] MQTT connect failed rc={rc}", file=sys.stderr)
            return
        cli.subscribe(topic, qos=0)
        print(f"[INFO] Subscribed topic={topic} broker={args.broker_host}:{args.broker_port}")

    def on_message(cli, userdata, msg):  # type: ignore[no-untyped-def]
        _ = cli
        _ = userdata
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            if args.verbose:
                print("[WARN] Ignoring non-JSON MQTT payload")
            return
        if args.verbose:
            print(f"[DEBUG] Event event_type={payload.get('event_type')} camera={payload.get('camera_id')}")
        if _is_match(payload, args.godown_id, args.camera_id):
            matches.put(payload)

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.broker_host, args.broker_port, keepalive=30)
    client.loop_start()
    try:
        deadline = time.monotonic() + max(5, args.timeout)
        seen = 0
        while time.monotonic() < deadline and seen < max(1, args.expected_count):
            try:
                event = matches.get(timeout=1.0)
            except Exception:
                continue
            seen += 1
            meta = event.get("meta") if isinstance(event.get("meta"), dict) else {}
            extra = meta.get("extra") if isinstance(meta, dict) and isinstance(meta.get("extra"), dict) else {}
            print(
                "[PASS] PERSON_LINE_CROSS "
                f"count={seen} event_id={event.get('event_id')} camera={event.get('camera_id')} "
                f"track_id={event.get('track_id')} line_id={extra.get('line_id')} direction={extra.get('direction')}"
            )
        if seen >= max(1, args.expected_count):
            print("[OK] Smoke test passed")
            return 0
        print(
            "[FAIL] Timed out waiting for PERSON_LINE_CROSS "
            f"(seen={seen}, expected={args.expected_count}, timeout={args.timeout}s)",
            file=sys.stderr,
        )
        return 1
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
