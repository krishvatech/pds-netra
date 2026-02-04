# Watchlist / Blacklist Person Detection

## Overview
PDS Netra now supports end-to-end blacklisted person detection. A watchlist person is managed centrally in the backend and synced to every edge node. When the edge detects a face match above threshold, it publishes a `FACE_MATCH` event. The backend stores the event, creates a `BLACKLIST_PERSON_MATCH` alert, and triggers notifications to HQ and the local Godown Manager.

## End-to-end flow
1. HQ adds a person to the watchlist in the Dashboard (`/dashboard/watchlist`).
2. Backend stores the person + reference images.
3. Edge nodes sync watchlist regularly or immediately on MQTT `pds/watchlist/sync`.
4. Edge runs face recognition; on match, it publishes a `FACE_MATCH` event (MQTT) and optionally posts HTTP fallback.
5. Backend stores the match, creates an alert, and notifies HQ + Godown Manager.

## Data contracts
**FACE_MATCH event** (schema_version `1.0`) is published by the edge:
- `event_id`, `occurred_at`, `godown_id`, `camera_id`, `event_type=FACE_MATCH`
- `payload.person_candidate`: `match_score`, `is_blacklisted`, `blacklist_person_id`, `embedding_hash`
- `payload.evidence`: `snapshot_url`, `local_snapshot_path`, `bbox`, `frame_ts`
- `correlation_id`

## How to add a blacklisted person
1. Open **Watchlist** in the dashboard.
2. Fill name/alias/reason and upload reference images (clear front-facing images work best).
3. The backend stores the images and notifies edges to sync.
4. If `EDGE_WATCHLIST_AUTO_EMBED=true`, edges will compute embeddings from the images and upload them back automatically.

## How a match becomes an alert
- Edge creates a `FACE_MATCH` event on match.
- Backend stores `face_match_events` and creates `BLACKLIST_PERSON_MATCH` alert with evidence metadata.
- Alerts are visible under **Alerts** and **Watchlist** tabs.

## Notifications
Notification recipients are resolved in this order:
1. `notification_recipients` table (role/channel/godown)
2. Env fallback
   - `WATCHLIST_NOTIFY_HQ_EMAILS`
   - `WATCHLIST_NOTIFY_HQ_WHATSAPP`
   - `WATCHLIST_NOTIFY_HQ_CALLS`
   - `WATCHLIST_NOTIFY_GODOWN_EMAILS=GDN_SAMPLE:gm@example.com;GDN_002:...`
   - `WATCHLIST_NOTIFY_GODOWN_WHATSAPP=GDN_SAMPLE:+91...`
   - `WATCHLIST_NOTIFY_GODOWN_CALLS=GDN_SAMPLE:+91...`

Providers:
- **Mock provider** (default, logs to stdout)
- **SMTP** (set `SMTP_HOST`, etc.)
- **WhatsApp webhook** (`WHATSAPP_WEBHOOK_URL`)

## Local dev notes
Backend `.env` additions:
```
ENABLE_WATCHLIST_MQTT_SYNC=true
WATCHLIST_STORAGE_BACKEND=local
WATCHLIST_STORAGE_DIR=./data/watchlist
WATCHLIST_IMAGE_BASE_URL=http://127.0.0.1:8001/media/watchlist
PDS_AUTH_DISABLED=true
```

Edge `.env` additions:
```
EDGE_WATCHLIST_ENABLED=true
EDGE_WATCHLIST_MIN_CONF=0.6
EDGE_WATCHLIST_SYNC_SEC=300
EDGE_WATCHLIST_COOLDOWN_SEC=120
EDGE_WATCHLIST_AUTO_EMBED=false
EDGE_WATCHLIST_HTTP_FALLBACK=false
```

## Retention & privacy
- Evidence is limited to snapshot images (no continuous storage by default).
- Alerts include minimal metadata (person_id, match_score, snapshot_url).
- Use standard data retention policies on `data/watchlist` and `data/snapshots`.
