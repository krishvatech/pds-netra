# pds-netra

Monorepo containing:
- `pds-netra-edge/` (edge AI + MQTT publisher)
- `pds-netra-backend/` (FastAPI + storage + REST APIs)
- `pds-netra-dashboard/` (Next.js dashboard)

## Local Mac setup (PoC)

### 1) MQTT broker (Mosquitto)
Option A: docker compose from edge folder
```bash
cd pds-netra-edge
docker compose up -d mosquitto
```

If port 1883 is already in use, change the host port:
```bash
docker run -d --name mosquitto -p 11883:1883 eclipse-mosquitto:2
```
Then set `MQTT_BROKER_PORT=11883` in your `.env` files.

### 2) Postgres (for backend data)
```bash
docker run -d --name pdsnetra-postgres \
  -e POSTGRES_USER=pdsnetra \
  -e POSTGRES_PASSWORD=pdsnetra \
  -e POSTGRES_DB=pdsnetra \
  -p 55432:5432 \
  postgres:14
```

### 3) Backend (FastAPI)
```bash
cd pds-netra-backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### 4) Edge node (with test-run override support)
```bash
cd pds-netra-edge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export EDGE_OVERRIDE_PATH=/Users/krishva/Projects/PDS-Netra-Project/pds-netra/pds-netra-backend/data/edge_overrides/GDN_001.json
python -m app.main --config config/pds_netra_config.yaml --device cpu --log-level INFO
```

### 5) Dashboard
```bash
cd pds-netra-dashboard
cp env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000 and use the Test Runs page to upload MP4s.
