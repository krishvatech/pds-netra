# 13 - Local Dev and Deployment

## Local development

### 1) Backend

```bash
cd pds-netra-backend
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

### 2) Worker

```bash
cd pds-netra-backend
python -m app.worker
```

### 3) Edge

```bash
cd pds-netra-edge
cp .env.example .env
python -m app.main --config config/pds_netra_config.yaml
```

### 4) Dashboard

```bash
cd pds-netra-dashboard
cp env.example .env.local
npm install
npm run dev
```

## Docker (edge only)

```bash
cd pds-netra-edge
docker compose up --build
```

This starts **Mosquitto + edge node** for local testing.

## PoC deployment steps (Pethapur)

1. **Edge node hardware**:
   - Jetson/Mac mini or equivalent.
2. **Network**:
   - 10 Mbps leased line with static IP for backend access.
3. **Backend hosting**:
   - State data center or approved cloud VM.
4. **Dashboard hosting**:
   - Separate VM or container.
5. **Configure envs**:
   - MQTT broker, DB, notification providers.

## Networking assumptions

- RTSP streams available on local LAN at godown.
- Edge node can reach MQTT broker and backend API.
