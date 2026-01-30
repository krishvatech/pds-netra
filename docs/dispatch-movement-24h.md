# Dispatch Movement SLA (ANPR Gate Sessions)

This document describes how the "movement not started within 24 hours" logic is handled using ANPR gate sessions when entry and exit share the same gate camera.

## Entry/Exit inference (single gate camera)
- The ANPR camera is configured with a gate line:
  - `anpr.gate_line`: two points `[(x1,y1),(x2,y2)]`
  - `anpr.inside_side`: which side of the line is inside (`POSITIVE` or `NEGATIVE`)
- For each plate detection, the plate center is tracked across frames.
- When the center crosses the line:
  - Outside → Inside = `ENTRY`
  - Inside → Outside = `EXIT`
- If direction cannot be inferred (`UNKNOWN`), the backend applies a fallback:
  - If there is an OPEN session for the plate and the last seen gap ≥ 10 minutes → treat as EXIT.
  - If no open session exists → treat as ENTRY.

## Event contract (edge → backend)
Edge publishes a new event type:
- `ANPR_HIT` (non-breaking; existing ANPR events remain)

Fields (EventModel + meta):
- `event_id`, `timestamp_utc`, `godown_id`, `camera_id`
- `meta.plate_text` (raw)
- `meta.plate_norm` (uppercase + alnum)
- `meta.direction`: `ENTRY` | `EXIT` | `UNKNOWN`
- `image_url` for evidence snapshots

## Vehicle gate session model
Backend stores sessions in `vehicle_gate_sessions`:
- `plate_raw`, `plate_norm`
- `entry_at`, `exit_at`, `status`
- `last_seen_at`, `entry_event_id`, `exit_event_id`
- `reminders_sent` json for 3/6/9/12/24 hour alerts

## Reminder schedule
Thresholds (configurable via `DISPATCH_MOVEMENT_THRESHOLDS_HOURS`):
- 3h, 6h, 9h, 12h (warning)
- 24h (critical)

Each threshold alert is created once per session and never duplicated.
If a session closes (EXIT), remaining reminders stop and existing open delay alerts are closed.

## Notifications
Alerts are sent to Godown Manager + HQ via WhatsApp and Email using the existing notification layer.

## Local testing
1) Start backend and dashboard.
2) Configure the ANPR gate line in `pds-netra-edge/config/pds_netra_config.yaml`.
3) Run edge and observe ANPR_HIT events.

### Simulate ANPR hit via HTTP
```
python pds-netra-edge/tools/simulate_anpr_hit.py \
  --backend-url http://localhost:8000 \
  --godown-id GDN_SAMPLE \
  --camera-id CAM_GATE_1 \
  --plate GJ01AB1234 \
  --direction ENTRY
```
Repeat with `--direction EXIT` to close the session.

## Configuration knobs
Backend:
- `DISPATCH_MOVEMENT_TIMEZONE=Asia/Kolkata`
- `DISPATCH_MOVEMENT_THRESHOLDS_HOURS=3,6,9,12,24`
- `DISPATCH_MOVEMENT_FALLBACK_EXIT=true`
- `DISPATCH_MOVEMENT_FALLBACK_EXIT_GAP_MIN=10`
- `ENABLE_VEHICLE_GATE_WATCHDOG=true`

Edge (YAML):
- `anpr.gate_line`
- `anpr.inside_side`
- `anpr.direction_max_gap_sec`
