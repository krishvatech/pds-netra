# PDS Netra Edge (Jetson) Runbook

## Layout on the Jetson
- Repo path: `/opt/pds-netra-edge`
- Config: `/opt/pds-netra-edge/config/pds_netra_config.yaml`
- Data: `/opt/pds-netra-edge/data/`
- Env file: `/opt/pds-netra-edge/.env`

## One-time setup
1. Copy the repo to `/opt/pds-netra-edge`.
2. Create required folders:
   - `sudo mkdir -p /opt/pds-netra-edge/config`
   - `sudo mkdir -p /opt/pds-netra-edge/data`
3. Place your YAML config at:
   - `/opt/pds-netra-edge/config/pds_netra_config.yaml`
4. Create `/opt/pds-netra-edge/.env` (see `pds-netra-edge/.env.example`).

## Enable auto-start on boot (systemd)
1. Install the service file:
   - `sudo cp /opt/pds-netra-edge/deployment/edge/systemd/pds-netra-edge.service.example /etc/systemd/system/pds-netra-edge.service`
2. Reload systemd and enable:
   - `sudo systemctl daemon-reload`
   - `sudo systemctl enable --now pds-netra-edge`
3. Check status and logs:
   - `sudo systemctl status pds-netra-edge`
   - `journalctl -u pds-netra-edge -f`

## Manual run (Docker Compose)
From `/opt/pds-netra-edge`:
- `docker compose -f /opt/pds-netra-edge/pds-netra-edge/docker-compose.jetson.yml up --build`

## Outbox Simulation
Use the helper script to simulate an MQTT outage and verify that the outbox buffers and replays events:
- `python /opt/pds-netra-edge/pds-netra-edge/tools/simulate_outage.py --config /opt/pds-netra-edge/config/pds_netra_config.yaml --events 25 --offline-host 127.0.0.1 --offline-port 1884 --online-host 127.0.0.1 --online-port 1883`

## Notes
- The compose file uses NVIDIA GPU access and runs with `--device cuda`.
- Outbox data and watchdog heartbeat are written to `/opt/pds-netra-edge/data/` so they survive reboots.
- Restart policy is handled by both Docker (`restart: unless-stopped`) and systemd (`Restart=always`).
