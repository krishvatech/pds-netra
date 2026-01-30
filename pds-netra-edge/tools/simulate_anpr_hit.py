"""
Simulate ANPR_HIT events for local testing.
"""

from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timezone

import urllib.request


def normalize_plate(text: str) -> str:
    return "".join(ch for ch in text.upper() if ch.isalnum())


def build_event(args: argparse.Namespace) -> dict:
    event_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    plate_raw = args.plate.strip().upper()
    plate_norm = normalize_plate(plate_raw)
    return {
        "godown_id": args.godown_id,
        "camera_id": args.camera_id,
        "event_id": event_id,
        "event_type": "ANPR_HIT",
        "severity": "info",
        "timestamp_utc": ts,
        "bbox": [10, 10, 120, 60],
        "track_id": 0,
        "image_url": args.snapshot_url,
        "clip_url": None,
        "meta": {
            "zone_id": None,
            "rule_id": "SIM_ANPR",
            "confidence": 0.9,
            "plate_text": plate_raw,
            "plate_norm": plate_norm,
            "direction": args.direction.upper(),
            "match_status": None,
            "extra": {}
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate ANPR_HIT event")
    parser.add_argument("--backend-url", default=os.getenv("EDGE_BACKEND_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--godown-id", default="GDN_SAMPLE")
    parser.add_argument("--camera-id", default="CAM_GATE_1")
    parser.add_argument("--plate", required=True)
    parser.add_argument("--direction", choices=["ENTRY", "EXIT", "UNKNOWN"], default="ENTRY")
    parser.add_argument("--snapshot-url", default=None)
    args = parser.parse_args()

    payload = build_event(args)
    url = args.backend_url.rstrip("/") + "/api/v1/edge/events"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            print(body)
            return 0
    except Exception as exc:
        print(f"Failed to post event: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
