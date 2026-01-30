# Notifications

This document describes the production notification flow for alerts (WhatsApp + Email) using an outbox pattern.
See `docs/notifications-routing.md` for the routing policy (Godown Manager realtime, HQ digest only).

## Overview
- Alerts are created by existing services (rules, watchlist, dispatch watchdog, etc.).
- When an alert is created, a **notification outbox** row is enqueued for each recipient/channel.
- A dedicated worker processes the outbox asynchronously, retries on failure, and logs delivery status.

## Data model
**notification_endpoints**
- `scope`: `HQ` or `GODOWN_MANAGER`
- `godown_id`: required for `GODOWN_MANAGER` scope
- `channel`: `WHATSAPP` or `EMAIL`
- `target`: phone number or email
- `is_enabled`: enable/disable delivery

**notification_outbox**
- One row per (alert, channel, target)
- Status lifecycle: `PENDING` → `SENT` or `RETRYING` → `FAILED`
- Retries with exponential backoff, max attempts configurable

## Configuration
Environment variables:
```
WHATSAPP_PROVIDER=log|http|twilio|meta
WHATSAPP_HTTP_URL=https://your-gateway.example/send
WHATSAPP_HTTP_TOKEN=optional-token

SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=user
SMTP_PASS=pass
SMTP_FROM=alerts@example.com
SMTP_USE_TLS=true

NOTIFY_WORKER_INTERVAL_SEC=10
NOTIFY_WORKER_BATCH_SIZE=50
NOTIFY_MAX_ATTEMPTS=5

DASHBOARD_BASE_URL=https://dashboard.example.com
```

If no provider is configured, the worker uses log providers and marks messages as sent (useful for local development).

## Recipient configuration
Use the API to configure HQ + godown manager recipients:

```
POST /api/v1/notification/endpoints
{
  "scope": "HQ",
  "channel": "EMAIL",
  "target": "hq@example.com",
  "is_enabled": true
}
```

```
POST /api/v1/notification/endpoints
{
  "scope": "GODOWN_MANAGER",
  "godown_id": "GDN_SAMPLE",
  "channel": "WHATSAPP",
  "target": "+91XXXXXXXXXX",
  "is_enabled": true
}
```

If endpoints are not configured, the system falls back to existing `notification_recipients` table or legacy env mappings.

## Run the worker
From `pds-netra-backend/`:
```
python -m app.worker
```

The worker polls the outbox every 10 seconds by default and retries failed sends.

## Verifying delivery
Use the alert delivery endpoint:
```
GET /api/v1/alerts/{alert_id}/deliveries
```

The dashboard shows delivery status on the alert detail page.
