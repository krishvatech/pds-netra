# AGENTS.md — PDS Netra Monorepo Ops Notes

## 1) Architecture and end-to-end flow
Monorepo components:
- `pds-netra-edge`: RTSP ingest, CV, MQTT publish, watchdog/outbox.
- `pds-netra-backend`: FastAPI + Postgres, MQTT/HTTP ingest, rules, alerts, notifications.
- `pds-netra-dashboard`: Next.js UI + API proxy to backend.

Primary entrypoints:
- Edge boot: `pds-netra-edge/app/main.py`
- Edge runtime loops: `pds-netra-edge/app/runtime/camera_loop.py`
- Backend boot: `pds-netra-backend/app/main.py`
- MQTT ingest: `pds-netra-backend/app/services/mqtt_consumer.py`
- Event ingest + persistence: `pds-netra-backend/app/services/event_ingest.py`
- Rule engine: `pds-netra-backend/app/services/rule_engine.py`
- Notification worker: `pds-netra-backend/app/worker.py`
- Dashboard proxy: `pds-netra-dashboard/app/api/v1/[...path]/route.ts`

Dataflow:
1. Edge reads RTSP/file frames in `Pipeline` and runs enabled detectors/processors.
2. Edge emits events via MQTT topics:
   - `pds/{godown_id}/events`
   - `pds/{godown_id}/presence`
   - `pds/{godown_id}/face-match`
   - `pds/{godown_id}/health`
3. Backend MQTT consumer (or HTTP fallback `/api/v1/edge/events`) validates and stores events.
4. Backend rule engine creates/updates alerts and enqueues notification outbox entries.
5. Worker sends notifications, retries failures, and creates HQ reports.
6. Dashboard fetches backend REST APIs through Next proxy and renders operations pages.

## 2) Edge pipelines currently in repo
- Fire detection:
  - `pds-netra-edge/app/cv/fire_detection.py`
  - Detects fire/smoke, confirms over multiple frames, emits `FIRE_DETECTED`.
- Animal intrusion:
  - `pds-netra-edge/app/rules/evaluator.py`
  - Zone/time aware animal class handling; emits intrusion alerts/events.
- After-hours presence:
  - `pds-netra-edge/app/presence/processor.py`
  - Person/vehicle presence sampling + cooldown; emits `PERSON_DETECTED` / `VEHICLE_DETECTED`.
- Tamper/obstruction/health:
  - `pds-netra-edge/app/cv/tamper.py`, scheduler/watchdog
  - Detects blackout, blur, lens block, moved camera, camera offline.
- Face/watchlist:
  - `pds-netra-edge/app/cv/face_id.py`, `app/watchlist/*`
  - Embedding/match flow with sync from backend; emits `FACE_MATCH`.
- ANPR:
  - `pds-netra-edge/app/cv/anpr.py`
  - Plate detection + OCR + rule evaluation + direction metadata.
- Bag movement:
  - `pds-netra-edge/app/cv/bag_movement.py`
  - Movement/odd-hours/unplanned/tally logic, emits `BAG_MOVEMENT`.

## 3) Exact run commands
### 3.1 Local PoC (mosquitto + postgres + backend + edge + dashboard)
From repo root:

```bash
# MQTT
cd pds-netra-edge
docker compose up -d mosquitto
```

```bash
# Postgres
docker run -d --name pdsnetra-postgres \
  -e POSTGRES_USER=pdsnetra \
  -e POSTGRES_PASSWORD=pdsnetra \
  -e POSTGRES_DB=pdsnetra \
  -p 55432:5432 \
  postgres:14
```

```bash
# Backend
cd pds-netra-backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

```bash
# Edge
cd pds-netra-edge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.main --config config/pds_netra_config.yaml --device cpu --log-level INFO
```

```bash
# Dashboard
cd pds-netra-dashboard
cp env.example .env.local
npm install
npm run dev
```

Open: `http://localhost:3000`

### 3.2 Jetson Orin Nano (4 RTSP cams, GPU compose + runbook)
Runbook base: `deployment/edge/README.md`

On Jetson host (one-time layout):
```bash
sudo mkdir -p /opt/pds-netra-edge/config
sudo mkdir -p /opt/pds-netra-edge/data
```

Place:
- config: `/opt/pds-netra-edge/config/pds_netra_config.yaml`
- env: `/opt/pds-netra-edge/.env`

Run with GPU compose (requested file):
```bash
cd /opt/pds-netra-edge/pds-netra-edge
docker compose -f docker-compose.jetson.gpu.yml up -d --build pds-edge mosquitto
```

Run with DeepStream profile (dedicated DS image + service):
```bash
cd /opt/pds-netra-edge/pds-netra-edge
docker compose -f docker-compose.jetson.gpu.yml --profile deepstream up -d --build pds-edge-deepstream mosquitto
```

Optional service auto-start (systemd from runbook):
```bash
sudo cp /opt/pds-netra-edge/deployment/edge/systemd/pds-netra-edge.service.example /etc/systemd/system/pds-netra-edge.service
# DeepStream option:
# sudo cp /opt/pds-netra-edge/deployment/edge/systemd/pds-netra-edge-deepstream.service.example /etc/systemd/system/pds-netra-edge.service
sudo systemctl daemon-reload
sudo systemctl enable --now pds-netra-edge
sudo systemctl status pds-netra-edge
journalctl -u pds-netra-edge -f
```

## 4) Test/verification status from this environment
- Backend tests: could not run (`pytest` missing in backend venv; package install blocked by offline/no-DNS environment).
- Edge tests: could not run (`pytest` missing in edge venv; package install blocked by offline/no-DNS environment).
- Dashboard lint: runs successfully after adding `.eslintrc.json`; currently emits warnings only.

## 5) Minimal code changes made in this pass
- Added `pds-netra-dashboard/.eslintrc.json` to enable non-interactive lint.
- Fixed backend report notification enqueue compatibility:
  - `pds-netra-backend/app/services/notification_outbox.py`
  - `enqueue_report_notifications` now supports both legacy and current call signatures (`message`, `message_text`, `email_html`, `scopes`, `godown_id`) so HQ report generation does not fail from keyword mismatch.

## 6) Optional production feature: DeepStream person pipeline (Phase 2B)
Status: implemented in edge runtime with real DeepStream path + flag-gated fallback.

What is in code now:
1. Person pipeline abstraction added:
   - `pds-netra-edge/app/cv/person_pipeline.py`
2. Runtime integration in callback:
   - `pds-netra-edge/app/runtime/camera_loop.py`
3. Toggle:
   - `EDGE_PERSON_PIPELINE=yolo|deepstream`
4. Fallback behavior:
   - if DeepStream path is unavailable/not implemented, pipeline logs once and falls back to YOLO persons automatically
5. Analytics (same event schema):
   - `PERSON_LINE_CROSS`
   - `PERSON_ROI_ENTER`
   - `PERSON_ROI_EXIT`
   - emitted through existing `EventModel` fields, no backend schema changes
6. DeepStream path details:
   - `appsrc -> nvstreammux -> nvinfer -> nvtracker -> fakesink`
   - parsed via `pyds` pad-probe and mapped to `DetectedObject`
   - required env: `EDGE_DEEPSTREAM_NVINFER_CONFIG`
   - dedicated image: `pds-netra-edge/docker/Dockerfile.deepstream.jp6`
   - compose profile service: `pds-edge-deepstream` in `pds-netra-edge/docker-compose.jetson.gpu.yml`
7. Jetson smoke helper:
   - `pds-netra-edge/tools/smoke_person_line_cross_mqtt.py`
   - subscribes to `pds/<godown_id>/events` and validates `PERSON_LINE_CROSS`

Key env flags:
- `EDGE_PERSON_PIPELINE=deepstream`
- `EDGE_PERSON_ROI_EVENTS_ENABLED=true`
- `EDGE_PERSON_ROI_ZONE_ID=<zone_id>` or `EDGE_PERSON_ROI_POLYGON=x,y;x,y;...`
- `EDGE_PERSON_LINE_CROSS_ENABLED=true`
- `EDGE_PERSON_LINE=x1,y1;x2,y2`
- `EDGE_PERSON_LINE_ID=<line_name>`
- `EDGE_PERSON_LINE_COOLDOWN_SEC=8`
- `EDGE_PERSON_LINE_MIN_MOTION_PX=6`
- `EDGE_DEEPSTREAM_NVINFER_CONFIG=<deepstream_nvinfer_config_path>`
- `EDGE_DEEPSTREAM_TRACKER_ENABLED=true`
- `EDGE_DEEPSTREAM_TRACKER_CONFIG=<tracker_config_path>`

## 7) Guardrails
- Never commit secrets from `.env`.
- Keep event schema backwards compatible (edge -> backend -> dashboard).
- Prefer additive flags for new pipelines; do not break existing camera role behavior.
