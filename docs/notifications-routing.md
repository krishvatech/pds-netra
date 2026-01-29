# Notifications Routing Policy

This document describes the PDS Netra notification routing rules.

## Policy
1) **Godown Manager** receives **all individual alerts** (WhatsApp + Email).
2) **HQ** receives **only digest reports** (WhatsApp + Email).
3) No HQ endpoint is used for individual alert pings.

Time zone: **Asia/Kolkata**.

## Data model
**notification_endpoints**
- `scope`: `GODOWN_MANAGER` or `HQ`
- `godown_id`: required for `GODOWN_MANAGER`
- `channel`: `WHATSAPP` or `EMAIL`
- `target`: phone number or email
- `is_enabled`: enable/disable delivery

**notification_outbox**
- `kind`: `ALERT` or `REPORT`
- `alert_id` for alert sends
- `report_id` for HQ digest sends
- Status lifecycle: `PENDING` → `SENT` or `RETRYING` → `FAILED`
- Deduped by unique constraints on `(alert_id, channel, target)` and `(report_id, channel, target)`

**alert_reports**
- Stores HQ digest reports (period, summary, text + HTML)

## Recipient configuration
Use the API:
```
POST /api/v1/notification/endpoints
{
  "scope": "GODOWN_MANAGER",
  "godown_id": "GDN_001",
  "channel": "WHATSAPP",
  "target": "+91XXXXXXXXXX",
  "is_enabled": true
}
```

```
POST /api/v1/notification/endpoints
{
  "scope": "HQ",
  "channel": "EMAIL",
  "target": "hq-alerts@example.com",
  "is_enabled": true
}
```

## Report schedule
Default schedules:
- Daily HQ report at **09:00 IST** (previous day 00:00–23:59 IST)
- Optional hourly report (disabled by default)

Env vars:
```
HQ_REPORT_DAILY_ENABLED=true
HQ_REPORT_DAILY_TIME=09:00
HQ_REPORT_HOURLY_ENABLED=false
HQ_REPORT_HOURLY_MINUTE=5
```

Manual report generation:
```
POST /api/v1/reports/hq/generate?period=24h
POST /api/v1/reports/hq/generate?period=1h
```

## Providers
WhatsApp:
```
WHATSAPP_PROVIDER=log|http
WHATSAPP_HTTP_URL=https://your-gateway.example/send
WHATSAPP_HTTP_TOKEN=optional-token
```

Email:
```
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=user
SMTP_PASS=pass
SMTP_FROM=alerts@example.com
SMTP_USE_TLS=true
```

If provider config is missing, the worker falls back to log providers (no crash).

## Worker
Run the worker process:
```
python -m app.worker
```

It handles:
1) Outbox delivery with retries
2) Scheduled HQ report generation
