# PDS Netra - DigitalOcean Deployment (Ubuntu 24.04)

This setup runs **backend + dashboard + mosquitto + Caddy** on the droplet.
Edge runs on your Jetson and connects to the droplet.

## 1) Droplet prerequisites

- Open firewall ports: `22`, `80`, `443`, `1883`.
- Point your domain (A record) to the droplet IP.

Install Docker:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```
Log out and back in after adding yourself to the docker group.

## 2) Clone repo + prepare env files

```bash
git clone <your-repo-url>
cd pds-netra/deployment
cp env/backend.env.prod.example env/backend.env
cp env/dashboard.env.prod.example env/dashboard.env
```

Edit `env/backend.env` with your **managed Postgres** connection and domain.
For local/PoC use, copy from the `*.dev.example` files instead.

## 2.1) Run DB migrations (required)

Run Alembic migrations against your configured database:

```bash
cd /path/to/pds-netra/pds-netra-backend
python -m app.scripts.run_migrations
```

Or via Docker Compose one-off service:

```bash
cd /path/to/pds-netra/deployment
docker compose -f docker-compose.prod.yml --profile migrate run --rm migrate
```

To create a new migration (backend changes):

```bash
cd /path/to/pds-netra/pds-netra-backend
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
```

## 3) Configure Mosquitto auth

Set a username/password for MQTT:

```bash
docker run --rm -it \
  -v $(pwd)/mosquitto/pwfile:/mosquitto/config/pwfile \
  eclipse-mosquitto:2 \
  mosquitto_passwd -b /mosquitto/config/pwfile your_mqtt_user your_mqtt_pass
```

Update `env/backend.env` and your Jetson `.env` with the same MQTT creds.

## 4) Configure Caddy

Create `deployment/.env` to feed Caddy:

```bash
cd /path/to/pds-netra/deployment
cat <<'EOT' > .env
CADDY_DOMAIN=your-domain.example
CADDY_EMAIL=you@example.com
EOT
```

## 5) Start services

From `deployment/`:

```bash
cd /path/to/pds-netra/deployment
docker compose -f docker-compose.prod.yml up -d --build
```

Caddy will automatically issue HTTPS certificates.

## 6) Jetson edge settings

Update `pds-netra-edge/.env` on your Jetson:

```
MQTT_BROKER_HOST=your-domain.example
MQTT_BROKER_PORT=1883
MQTT_USERNAME=your_mqtt_user
MQTT_PASSWORD=your_mqtt_pass
EDGE_BACKEND_URL=https://your-domain.example
EDGE_SNAPSHOT_BASE_URL=https://your-domain.example/media/snapshots
EDGE_BACKEND_TOKEN=<same as PDS_AUTH_TOKEN>
```

Restart edge after updating.

## 7) Sanity checks

- Open `https://your-domain.example` for dashboard.
- MQTT traffic from edge should create events/alerts in backend.

If you need to debug backend quickly (optional):

```bash
docker compose -f deployment/docker-compose.prod.yml logs -f backend
```

## Production checklist

- Set `PDS_ENV=prod`.
- `PDS_AUTH_DISABLED=false` and a strong `PDS_AUTH_TOKEN` (>=20 chars, not demo/change-me).
- `AUTO_CREATE_DB=false`, `AUTO_SEED_* = false` unless explicitly needed.
- `ENABLE_MQTT_CONSUMER=false` and `ENABLE_DISPATCH_*` disabled unless explicitly required.
- Supply secrets via env/secret store; never commit real values.
- Set `EDGE_BACKEND_TOKEN` on Jetson to match `PDS_AUTH_TOKEN`.
- MQTT port `1883` is exposed for edge connectivity. Restrict it with firewall rules and plan TLS/ACLs if public.

## PoC local quickstart

```bash
cd pds-netra/deployment
cp env/backend.env.dev.example env/backend.env
cp env/dashboard.env.dev.example env/dashboard.env
docker compose -f docker-compose.prod.yml up -d --build
```

## Manual DB setup / seeding (optional)

Run these from `pds-netra-backend/` when you want explicit control:

```bash
python -m app.scripts.create_db
python -m app.scripts.seed_demo_data
```
