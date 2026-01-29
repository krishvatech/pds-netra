# 05 - Backend

## Run the backend

```bash
cd pds-netra-backend
uvicorn app.main:app --reload
```

### Apply migrations

```bash
cd pds-netra-backend
alembic upgrade head
```

## Database schema (key tables)

- `godowns`
- `cameras` (includes `role`, `rtsp_url`, `modules_json`)
- `events`
- `alerts`
- `alert_event_links`
- `vehicle_gate_sessions`
- `notification_endpoints`
- `notification_outbox`
- `alert_reports`
- `watchlist_persons`, `watchlist_person_images`, `watchlist_embeddings`, `face_match_events`
- `after_hours_policies`, `after_hours_policy_audit`
- `dispatch_issues`

## Core APIs (verified routes)

### Events + Alerts

- `GET /api/v1/events` - list events
- `GET /api/v1/alerts` - list alerts
- `GET /api/v1/alerts/{alert_id}` - alert detail
- `POST /api/v1/alerts/{alert_id}/ack` - acknowledge alert
- `GET /api/v1/alerts/{alert_id}/deliveries` - notification delivery status
- `GET /api/v1/alerts/{alert_id}/actions` - alert actions list
- `POST /api/v1/alerts/{alert_id}/actions` - add alert action

### Edge ingest (HTTP fallback)

- `POST /api/v1/edge/events`
  - Supports `FACE_MATCH`, `PERSON_DETECTED`, `VEHICLE_DETECTED`, `ANPR_HIT`, `ANIMAL_*`, `FIRE_DETECTED`.

### Cameras

- `GET /api/v1/cameras` - list cameras (role + modules)
- `POST /api/v1/cameras` - create camera
- `PUT /api/v1/cameras/{camera_id}` - update camera
- `GET /api/v1/cameras/{camera_id}/zones` - get zones
- `PUT /api/v1/cameras/{camera_id}/zones` - update zones

### Watchlist / Blacklist

- `GET /api/v1/watchlist/persons`
- `POST /api/v1/watchlist/persons` (multipart upload)
- `PATCH /api/v1/watchlist/persons/{person_id}`
- `POST /api/v1/watchlist/persons/{person_id}/images`
- `POST /api/v1/watchlist/persons/{person_id}/embeddings`
- `GET /api/v1/watchlist/persons/{person_id}/matches`
- `GET /api/v1/watchlist/sync`

### After-hours policies

- `GET /api/v1/after-hours/policies`
- `POST /api/v1/after-hours/policies`
- `PATCH /api/v1/after-hours/policies/{policy_id}`

### Vehicle gate sessions

- `GET /api/v1/vehicle-gate-sessions`

### Notifications

- `GET /api/v1/notification/endpoints`
- `POST /api/v1/notification/endpoints`
- `PATCH /api/v1/notification/endpoints/{endpoint_id}`
- `DELETE /api/v1/notification/endpoints/{endpoint_id}`

### Reports (HQ digest)

- `GET /api/v1/reports/hq`
- `GET /api/v1/reports/hq/{id}`
- `GET /api/v1/reports/hq/{id}/deliveries`
- `POST /api/v1/reports/hq/generate?period=24h|1h`

## Background workers / schedulers

- **MQTT consumer**: starts in `app.main` if `ENABLE_MQTT_CONSUMER=true`.
- **Dispatch watchdog**: periodic evaluation of movement delays.
- **Dispatch plan sync**: optional plan refresh.
- **Notification worker**: `python -m app.worker` (outbox delivery + HQ reports).

## Idempotency and dedupe

- Events are deduped by `event_id` for key event types.
- Notification outbox has unique constraints:
  - (alert_id, channel, target)
  - (report_id, channel, target)

## Authentication (PoC)

- Header-based lightweight auth in `app/core/auth.py`.
- Default: `PDS_AUTH_DISABLED=true` in `.env.example` (PoC-friendly).
- For protected endpoints, provide:
  - `Authorization: Bearer <token>`
  - `X-User-Role`, `X-User-Godown`, `X-User-District`

## Not implemented yet

- **Weighbridge integration**: not present in current backend services or APIs.
  - Intended: ingest weighbridge weights and correlate with dispatch sessions.
