# 06 - Dashboard

## How officials use the dashboard

- **Godown Manager:** focuses on real-time alerts and evidence.
- **HQ/District:** reviews trends, digests, and compliance.

## Main pages (verified)

- **Command Center** - high-level operational view.
- **Overview** - KPIs and summary.
- **Godowns** - per-godown status and camera list.
- **Cameras** - camera roles and enabled modules.
- **Alerts** - filter by type, severity, status, dates.
- **After-hours** - after-hours alerts and policies.
- **Watchlist** - blacklist persons and matches.
- **Animals** - animal intrusion alerts.
- **Fire** - fire alerts.
- **Incidents** - consolidated incident list.
- **Reports** - HQ digest reports and delivery status.
- **Health** - camera health and offline signals.
- **Rules** - rule configuration view.
- **Notifications** - endpoints management (HQ / Godown Manager).
- **Dispatch Movement** - gate ANPR sessions and delay alerts.
- **Dispatch** - dispatch analytics.
- **Live Cameras** - live snapshots.
- **Test Runs** - test video runs and annotated outputs.

## Filters and evidence

- Alerts and events provide **snapshot evidence** if available.
- Filters include **godown**, **camera**, **alert type**, **severity**, **time range**.

## Delivery visibility

- Alert detail page shows **notification delivery status** per channel.
- HQ Reports page shows **digest generation** and delivery status.

## RBAC expectations

- **STATE_ADMIN / HQ_ADMIN**: manage watchlist, notifications, policies, reports.
- **GODOWN_MANAGER**: view their own godown alerts and sessions.

> Note: PoC auth is header-based; production RBAC should integrate with SSO or state IAM.
