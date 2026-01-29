# 08 - Rules and Alerts

## Alert taxonomy (backend)

The backend maps raw events to alert types:

- **SECURITY_UNAUTH_ACCESS** (from UNAUTH_PERSON / LOITERING / FACE_UNKNOWN_ACCESS)
- **AFTER_HOURS_PERSON_PRESENCE**
- **AFTER_HOURS_VEHICLE_PRESENCE**
- **ANIMAL_INTRUSION** (from ANIMAL_INTRUSION / ANIMAL_DETECTED)
- **FIRE_DETECTED**
- **BLACKLIST_PERSON_MATCH**
- **OPERATION_BAG_MOVEMENT_ANOMALY**
- **OPERATION_UNPLANNED_MOVEMENT**
- **DISPATCH_MOVEMENT_DELAY** (vehicle stayed beyond threshold)
- **CAMERA_HEALTH_ISSUE** (offline/tamper/low light)
- **ANPR_MISMATCH_VEHICLE**

## Rule logic (simplified)

### After-hours presence (edge + backend)

- **Edge** emits `PERSON_DETECTED` and `VEHICLE_DETECTED` events when:
  - Time is outside configured day window (`EDGE_AFTER_HOURS_DAY_START/END`).
  - Default window is **09:00-19:00 IST** -> alerts after 19:00.
- **Backend** converts these into alerts:
  - `AFTER_HOURS_PERSON_PRESENCE`
  - `AFTER_HOURS_VEHICLE_PRESENCE`

### Dispatch movement delay (backend)

- **Entry**: first ANPR hit with ENTRY opens a session.
- **Exit**: ANPR EXIT closes the session.
- **Reminders**: thresholds from `DISPATCH_MOVEMENT_THRESHOLDS_HOURS` (default `3,6,9,12,24`).
- **Alert type**: `DISPATCH_MOVEMENT_DELAY` per threshold.

### Animal intrusion (edge + backend)

- **Edge** detects animal classes (dog/cat/cow/buffalo/monkey etc.)
- **Night severity** is higher by default (`EDGE_ANIMAL_NIGHT_*`).
- **Backend** consolidates into `ANIMAL_INTRUSION` alerts.
- For night monitoring, **IR cameras** are recommended at perimeter areas.

### Fire detection (edge + backend)

- **Edge** uses multi-frame confirmation and cooldown:
  - `EDGE_FIRE_MIN_FRAMES`, `EDGE_FIRE_COOLDOWN_SEC`
- **Backend** creates `FIRE_DETECTED` alerts (severity: critical).

### Blacklist (watchlist)

- **Edge** emits `FACE_MATCH` with match score and evidence.
- **Backend** creates `BLACKLIST_PERSON_MATCH` for blacklisted matches.

## Dedupe / cooldown policy

- **Edge-level** cooldowns:
  - Animal species cooldown (`EDGE_ANIMAL_SPECIES_COOLDOWN_SEC`)
  - After-hours cooldown per person/vehicle
  - Fire cooldown (`EDGE_FIRE_COOLDOWN_SEC`)

- **Backend-level** dedupe:
  - Alert reuse within a **10-minute window** for same alert type and location.
  - Dispatch movement alerts deduped by plate + threshold.

## Evidence requirements

- Snapshot URL when available
- Optional clip URL if implemented in future
- For fire/animal/after-hours: include bounding boxes in meta where available

## Not implemented yet

- **Weighbridge rule checks**: no backend rule processor exists yet.
