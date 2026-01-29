# PDS Netra Documentation Pack

This documentation pack covers the PoC at **Pethapur Godown (Gandhinagar)** and a scalable rollout to ~7000 cameras statewide. It is written for government officials and technical teams.

## Repo inventory (verified)

- **Monorepo root:** `pds-netra/`
- **Edge node:** `pds-netra-edge/`
  - Config: `pds-netra-edge/config/pds_netra_config.yaml`
  - Env: `pds-netra-edge/.env.example`
  - Docker: `pds-netra-edge/docker-compose.yml`
- **Backend:** `pds-netra-backend/`
  - FastAPI app: `pds-netra-backend/app/main.py`
  - Env: `pds-netra-backend/.env.example`
  - Worker: `pds-netra-backend/app/worker.py`
  - Migrations: `pds-netra-backend/alembic/versions/*`
- **Dashboard:** `pds-netra-dashboard/`
  - Next.js App Router: `pds-netra-dashboard/app/dashboard/*`
  - Env: `pds-netra-dashboard/env.example`

## Key commands (local)

- **Edge (RTSP + CV):**
  ```bash
  cd pds-netra-edge
  python -m app.main --config config/pds_netra_config.yaml --device cpu
  ```
- **Backend API:**
  ```bash
  cd pds-netra-backend
  uvicorn app.main:app --reload
  ```
- **Notification worker (outbox + HQ digest):**
  ```bash
  cd pds-netra-backend
  python -m app.worker
  ```
- **Dashboard:**
  ```bash
  cd pds-netra-dashboard
  npm install
  npm run dev
  ```

## Ports (defaults)

- **MQTT broker:** 1883
- **Backend API:** 8001
- **Dashboard:** 3000
- **PostgreSQL (example):** 55432 (from `.env.example`)

---

# Documentation index

1. [System Overview](01-system-overview.md)
2. [Architecture](02-architecture.md)
3. [Camera Roles and Pipelines](03-camera-roles-and-pipelines.md)
4. [Edge Node](04-edge-node.md)
5. [Backend](05-backend.md)
6. [Dashboard](06-dashboard.md)
7. [Event Schemas](07-event-schemas.md)
8. [Rules and Alerts](08-rules-and-alerts.md)
9. [Notifications Routing](09-notifications-routing.md)
10. [Privacy and Security](10-privacy-security.md)
11. [PoC Execution Plan (3 months)](11-poc-execution-plan.md)
12. [Runbook / Operations](12-runbook-ops.md)
13. [Local Dev and Deployment](13-local-dev-and-deploy.md)
14. [Demo Script](14-demo-script.md)

## Supplementary (legacy) notes

These are earlier technical notes kept for reference:

- [After-hours presence](after-hours-presence-rule.md)
- [Animal intrusion](animal-intrusion.md)
- [Camera roles (legacy)](camera-roles-and-pipelines.md)
- [Dispatch movement](dispatch-movement-24h.md)
- [Fire detection](fire-detection.md)
- [Notifications routing (legacy)](notifications-routing.md)
- [Notifications (legacy)](notifications.md)
- [Watchlist/blacklist](watchlist-blacklist.md)
