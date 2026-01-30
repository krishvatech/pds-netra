"""
Simulate FIRE_DETECTED events for local testing.
"""

from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timezone

import urllib.request


def build_event(args: argparse.Namespace) -> dict:
    event_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    classes = [c.strip() for c in args.classes.split(",") if c.strip()]
    if not classes:
        classes = ["fire"]
    return {
        "godown_id": args.godown_id,
        "camera_id": args.camera_id,
        "event_id": event_id,
        "event_type": "FIRE_DETECTED",
        "severity": "critical",
        "timestamp_utc": ts,
        "bbox": [10, 10, 120, 120],
        "track_id": 0,
        "image_url": args.snapshot_url,
        "clip_url": None,
        "meta": {
            "zone_id": None,
            "rule_id": "FIRE_DETECTED",
            "confidence": float(args.confidence),
            "fire_classes": classes,
            "fire_confidence": float(args.confidence),
            "fire_bboxes": [[10, 10, 120, 120]],
            "fire_model_name": "yolo26",
            "fire_model_version": None,
            "fire_weights_id": args.weights_id,
            "extra": {"schema_version": "1.0"}
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate FIRE_DETECTED event")
    parser.add_argument("--backend-url", default=os.getenv("EDGE_BACKEND_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--godown-id", default="GDN_SAMPLE")
    parser.add_argument("--camera-id", default="CAM_FIRE_1")
    parser.add_argument("--classes", default="fire")
    parser.add_argument("--confidence", type=float, default=0.85)
    parser.add_argument("--snapshot-url", default=None)
    parser.add_argument("--weights-id", default="fire.pt")
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
