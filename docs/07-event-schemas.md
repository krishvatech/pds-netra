# 07 - Event Schemas

> Time zone reference: **Asia/Kolkata** for human display. All timestamps are stored in UTC ISO format.

## Event families (as implemented)

### A) General events (MQTT `pds/{godown_id}/events`)

These use the `EventModel` structure from `pds-netra-edge/app/models/event.py` and `pds-netra-backend/app/schemas/event.py`.

**Required fields**
- `godown_id`, `camera_id`, `event_id`, `event_type`, `severity`, `timestamp_utc`, `meta`.

**Optional fields**
- `bbox`, `track_id`, `image_url`, `clip_url`.

### B) Presence events (MQTT `pds/{godown_id}/presence`)

These use `PresenceEvent` (`schema_version=1.0`).

### C) Watchlist face match events (MQTT `pds/{godown_id}/face-match`)

These use `FaceMatchEvent` (`schema_version=1.0`).

---

## JSON examples

### ANPR_HIT (general event)

```json
{
  "godown_id": "GDN_SAMPLE",
  "camera_id": "CAM_GATE_1",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "ANPR_HIT",
  "severity": "info",
  "timestamp_utc": "2026-01-29T03:15:00Z",
  "bbox": [120, 300, 420, 480],
  "track_id": 12,
  "image_url": "http://127.0.0.1:8001/media/snapshots/GDN_SAMPLE/....jpg",
  "clip_url": null,
  "meta": {
    "zone_id": "gate_outer",
    "rule_id": "ANPR_MONITOR",
    "confidence": 0.87,
    "plate_text": "GJ01AB1234",
    "plate_norm": "GJ01AB1234",
    "direction": "ENTRY",
    "match_status": "UNKNOWN",
    "extra": {
      "schema_version": "1.0",
      "correlation_id": "f0c8d2c1-9d5a-4e8c-9b0e-1f9cfdbd1234"
    }
  }
}
```

### PERSON_DETECTED (presence event)

```json
{
  "schema_version": "1.0",
  "event_id": "1b2c3d4e-1111-2222-3333-444455556666",
  "occurred_at": "2026-01-29T14:12:00Z",
  "timezone": "Asia/Kolkata",
  "godown_id": "GDN_SAMPLE",
  "camera_id": "CAM_AISLE_3",
  "event_type": "PERSON_DETECTED",
  "payload": {
    "count": 1,
    "bbox": [[400, 200, 520, 520]],
    "confidence": 0.72,
    "is_after_hours": true,
    "evidence": {
      "snapshot_url": "http://127.0.0.1:8001/media/snapshots/GDN_SAMPLE/....jpg",
      "local_path": null,
      "frame_ts": "2026-01-29T14:12:00Z"
    }
  },
  "correlation_id": "f1a2b3c4-5555-6666-7777-888899990000"
}
```

### VEHICLE_DETECTED (presence event)

Same as `PERSON_DETECTED` with `event_type = VEHICLE_DETECTED` and vehicle bbox list.

### ANIMAL_DETECTED / ANIMAL_INTRUSION (general event)

```json
{
  "godown_id": "GDN_SAMPLE",
  "camera_id": "CAM_AISLE_3",
  "event_id": "fdb2d3e4-aaaa-bbbb-cccc-ddddeeeeffff",
  "event_type": "ANIMAL_INTRUSION",
  "severity": "critical",
  "timestamp_utc": "2026-01-29T02:45:00Z",
  "bbox": [120, 250, 360, 520],
  "track_id": 7,
  "image_url": "http://127.0.0.1:8001/media/snapshots/GDN_SAMPLE/....jpg",
  "meta": {
    "zone_id": "aisle_zone3",
    "rule_id": "RULE_ANIMAL_INTRUSION",
    "confidence": 0.81,
    "animal_species": "cow",
    "animal_count": 1,
    "animal_is_night": true,
    "animal_bboxes": [[120, 250, 360, 520]],
    "extra": {}
  }
}
```

### FIRE_DETECTED (general event)

```json
{
  "godown_id": "GDN_SAMPLE",
  "camera_id": "CAM_AISLE_3",
  "event_id": "3a1b0c9d-1234-4567-89ab-cdef12345678",
  "event_type": "FIRE_DETECTED",
  "severity": "critical",
  "timestamp_utc": "2026-01-29T04:05:00Z",
  "bbox": [200, 300, 450, 600],
  "image_url": "/Users/.../snapshots/...jpg",
  "meta": {
    "zone_id": "aisle_zone3",
    "rule_id": "FIRE_DETECTED",
    "confidence": 0.91,
    "fire_classes": ["fire", "smoke"],
    "fire_confidence": 0.91,
    "fire_bboxes": [[200, 300, 450, 600]],
    "fire_model_name": "yolo26",
    "fire_weights_id": "fire.pt",
    "extra": {
      "schema_version": "1.0",
      "correlation_id": "c5d1c1ff-1111-2222-3333-444455556666",
      "local_snapshot_path": "/Users/.../snapshots/...jpg"
    }
  }
}
```

### FACE_MATCH / BLACKLIST_PERSON_MATCH (watchlist event)

```json
{
  "schema_version": "1.0",
  "event_id": "9c1d2e3f-aaaa-bbbb-cccc-ddddeeeeffff",
  "occurred_at": "2026-01-29T05:05:00Z",
  "godown_id": "GDN_SAMPLE",
  "camera_id": "CAM_AISLE_3",
  "event_type": "FACE_MATCH",
  "payload": {
    "person_candidate": {
      "embedding_hash": "hash123",
      "match_score": 0.92,
      "is_blacklisted": true,
      "blacklist_person_id": "WLP-0001"
    },
    "evidence": {
      "snapshot_url": "http://127.0.0.1:8001/media/snapshots/GDN_SAMPLE/....jpg",
      "local_snapshot_path": null,
      "bbox": [120, 60, 210, 170],
      "frame_ts": "2026-01-29T05:05:00Z"
    }
  },
  "correlation_id": "7f7c1d0a-1234-5678-9012-abcdefabcdef"
}
```

## Idempotency rules

- `event_id` is treated as the idempotency key for duplicate protection.
- For presence and face match events, `event_id` is required and unique.

## Not implemented yet

- **Weighbridge events**: no schema currently defined in this repo.
