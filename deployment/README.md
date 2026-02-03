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
cp env/backend.env.example env/backend.env
cp env/dashboard.env.example env/dashboard.env
```

Edit `env/backend.env` with your **managed Postgres** connection and domain.

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
```

Restart edge after updating.

## 7) Sanity checks

- Open `https://your-domain.example` for dashboard.
- MQTT traffic from edge should create events/alerts in backend.

If you need to debug backend quickly (optional):

```bash
docker compose -f deployment/docker-compose.prod.yml logs -f backend
```
