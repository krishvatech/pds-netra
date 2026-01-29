# Fire Detection

This document describes the fire/smoke detection flow in PDS Netra.

## Configuration (edge)
Add a fire section in `pds-netra-edge/config/pds_netra_config.yaml`:

```
fire_detection:
  enabled: false
  model_path: "models/fire.pt"
  device: "cpu"
  conf: 0.35
  iou: 0.45
  cooldown_seconds: 60
  min_frames_confirm: 3
  zones_enabled: false
  interval_sec: 1.5
  class_keywords: ["fire", "smoke"]
  save_snapshot: true
```

Environment overrides (optional):
- `EDGE_FIRE_ENABLED`
- `EDGE_FIRE_MODEL_PATH`
- `EDGE_FIRE_DEVICE`
- `EDGE_FIRE_CONF`
- `EDGE_FIRE_IOU`
- `EDGE_FIRE_COOLDOWN_SEC`
- `EDGE_FIRE_MIN_FRAMES`
- `EDGE_FIRE_ZONES_ENABLED`
- `EDGE_FIRE_INTERVAL_SEC`
- `EDGE_FIRE_CLASS_KEYWORDS`
- `EDGE_FIRE_SAVE_SNAPSHOT`

## Model weights
- Place the fire model weights at the configured `model_path`.
- If the file is missing or cannot be loaded, the edge logs a warning and skips fire detection.

## Detection logic
- Fire detection is throttled by `interval_sec` to reduce load.
- A fire event is emitted only after `min_frames_confirm` detections within a short window.
- After an alert is emitted, a per-camera cooldown prevents spamming (`cooldown_seconds`).

## Event contract
Edge publishes `FIRE_DETECTED` using the existing event envelope:
- `event_type: FIRE_DETECTED`
- `event_id`, `timestamp_utc`, `godown_id`, `camera_id`
- `meta.fire_classes`, `meta.fire_confidence`, `meta.fire_bboxes`
- `meta.fire_model_name`, `meta.fire_weights_id`
- `image_url` (snapshot evidence when available)

## Backend behavior
- Ingests `FIRE_DETECTED` events and creates alerts.
- Dedupe: if an OPEN fire alert exists for the same camera, it updates `last_seen_at` and evidence.
- Cooldown: new alerts are suppressed within the cooldown window (`FIRE_ALERT_COOLDOWN_SEC`, default 600s).
- Notifications: WhatsApp + Email to Godown Manager + HQ.

## Dashboard
- Fire alerts are visible under `/dashboard/fire` and `/dashboard/alerts`.
- Overview includes Fire alerts (24h / 7d).

## Simulate a fire event
You can post a mock event to the backend:
```
curl -X POST http://localhost:8000/api/v1/edge/events \
  -H "Content-Type: application/json" \
  -d '{
    "godown_id": "GDN_001",
    "camera_id": "CAM_FIRE_1",
    "event_id": "evt-fire-001",
    "event_type": "FIRE_DETECTED",
    "severity": "critical",
    "timestamp_utc": "2026-01-28T12:00:00Z",
    "bbox": [10, 10, 120, 120],
    "track_id": 0,
    "image_url": "http://localhost/fire.jpg",
    "clip_url": null,
    "meta": {
      "zone_id": null,
      "rule_id": "FIRE_DETECTED",
      "confidence": 0.92,
      "fire_classes": ["fire"],
      "fire_confidence": 0.92,
      "fire_bboxes": [[10, 10, 120, 120]],
      "fire_model_name": "yolo26",
      "fire_weights_id": "fire.pt",
      "extra": {"schema_version": "1.0"}
    }
  }'
```
