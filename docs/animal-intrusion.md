# Animal Intrusion Detection

This document describes how animal intrusion alerts are generated end-to-end in PDS Netra.

## Rule definition
- Event type: `ANIMAL_INTRUSION` (edge publishes using the existing animal detector).
- Species supported: dog, cat, cow, buffalo, monkey, deer, donkey and other common classes.
- Night logic (default): 19:00–06:00 in `Asia/Kolkata`.
- Severity:
  - Night: `critical`
  - Day: `warning` (configurable)

## Data contract (edge -> backend)
Event payload is published using the existing event schema, with these metadata fields:
- `animal_species` (string)
- `animal_count` (number)
- `animal_confidence` (number)
- `animal_is_night` (boolean, edge computed; backend recomputes as source of truth)
- `animal_bboxes` (list of bboxes)
- `snapshot_url` (when evidence is saved)

## Dedupe strategy
- Edge: per-camera and per-species cooldown (default 60s).
- Backend: per godown + camera + species cooldown (default 300s).
- If an OPEN/ACK alert exists for the same species, new events update `last_seen_at` and evidence instead of creating a new alert.

## Configuration
Edge (`pds-netra-edge/.env`):
- `EDGE_ANIMAL_SPECIES_COOLDOWN_SEC=60`
- `EDGE_ANIMAL_NIGHT_START=19:00`
- `EDGE_ANIMAL_NIGHT_END=06:00`
- `EDGE_ANIMAL_NIGHT_SEVERITY=critical`
- `EDGE_ANIMAL_DAY_SEVERITY=warning`

Backend (`pds-netra-backend/.env`):
- `ANIMAL_TIMEZONE=Asia/Kolkata`
- `ANIMAL_NIGHT_START=19:00`
- `ANIMAL_NIGHT_END=06:00`
- `ANIMAL_ALERT_COOLDOWN_SEC=300`
- `ANIMAL_DAY_SEVERITY=warning`

## Dashboard
- Animal intrusion alerts are visible in:
  - `/dashboard/animals`
  - `/dashboard/alerts` and alert detail pages
- Evidence thumbnails link to snapshots when available.

## Local test flow
1. Start backend and dashboard.
2. Run edge with an `ANIMAL_FORBIDDEN` rule enabled in `pds-netra-edge/config/pds_netra_config.yaml`.
3. When an animal is detected in a forbidden zone, the edge publishes an `ANIMAL_INTRUSION` event.
4. Backend stores the event, creates/updates an alert, and triggers notifications.

## Simulate an event (HTTP fallback)
You can also POST a mock event to the backend:
```
curl -X POST http://localhost:8000/api/v1/edge/events \
  -H "Content-Type: application/json" \
  -d '{
    "godown_id": "GDN_001",
    "camera_id": "CAM_GATE_1",
    "event_id": "evt-animal-001",
    "event_type": "ANIMAL_INTRUSION",
    "severity": "warning",
    "timestamp_utc": "2026-01-01T14:30:00Z",
    "bbox": [10, 10, 120, 120],
    "track_id": 1,
    "image_url": "http://localhost/snap.jpg",
    "clip_url": null,
    "meta": {
      "zone_id": "gate_outer",
      "rule_id": "RULE_ANIMAL_INTRUSION_GATE",
      "confidence": 0.82,
      "movement_type": null,
      "plate_text": null,
      "match_status": null,
      "reason": null,
      "person_id": null,
      "person_name": null,
      "person_role": null,
      "animal_species": "cow",
      "animal_count": 1,
      "animal_confidence": 0.82,
      "animal_is_night": true,
      "animal_bboxes": [[10, 10, 120, 120]],
      "extra": {}
    }
  }'
```
