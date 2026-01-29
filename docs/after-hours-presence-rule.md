# After-hours Presence Rule

## Rule definition
- Timezone: Asia/Kolkata
- Operations allowed: 09:00-19:00
- After-hours (>= 19:00 or < 09:00): **no persons** and **no vehicles** allowed inside the godown.
- Any person or vehicle detected after-hours triggers an alert immediately.

## Event types (schema_version 1.0)
- `PERSON_DETECTED`
- `VEHICLE_DETECTED`
- (optional) `ANPR_HIT` if plate hits are emitted by the edge.

Payload fields:
- `count`: number of persons/vehicles detected
- `bbox`: list of bboxes (optional)
- `confidence`: optional
- `is_after_hours`: optional edge-computed hint (backend is source of truth)
- `evidence`: snapshot URL/path + frame timestamp
- `correlation_id` for tracing

## Dedup strategy
- Backend stores all presence events (idempotent by `event_id`).
- Alerts are deduped per `(godown_id, camera_id, alert_type)`:
  - If an OPEN/ACK alert exists, it is updated with `last_seen_at` and evidence.
  - Otherwise, a new alert is created if outside the cooldown window (default 120s).

## Policy configuration
- Per-godown overrides live in the `after_hours_policies` table.
- If no row exists for a godown, backend falls back to env defaults:
  - `AFTER_HOURS_DAY_START=09:00`
  - `AFTER_HOURS_DAY_END=19:00`
  - `AFTER_HOURS_PRESENCE_ALLOWED=false`
  - `AFTER_HOURS_ALERT_COOLDOWN_SEC=120`

## Admin API (HQ/State Admin)
- `GET /api/v1/after-hours/policies/{godown_id}` returns current policy (default or override).
- `PUT /api/v1/after-hours/policies/{godown_id}` updates policy (upsert).
- `GET /api/v1/after-hours/policies?godown_id=...` lists overrides.

## Notifications
- WhatsApp + Email are sent to:
  - Godown Manager
  - HQ
- Recipients are resolved via `notification_recipients` table, then env fallback.

## Local test flow
1) Configure edge:
   - Enable `after_hours_presence` in `pds-netra-edge/config/pds_netra_config.yaml`.
   - For quick testing, set `day_start`/`day_end` to a short window around current time.
2) Start backend and edge.
3) Trigger a person or vehicle after-hours.
4) Verify:
   - Event stored in `/api/v1/events`
   - Alert appears in `/api/v1/alerts`
   - Evidence snapshot is linked
   - Notifications logged (mock provider) if real providers not configured
