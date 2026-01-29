# 10 - Privacy and Security

This section is written to align with government policy expectations for surveillance systems.

## Privacy-by-design principles

1) Data minimization
   - Store events and alerts, not continuous video.
   - Capture snapshots only when an alert is created.

2) Purpose limitation
   - Use data only for godown safety, compliance, and public distribution integrity.

3) Access control
   - Separate access for Godown Managers and HQ.
   - Sensitive watchlist data restricted to HQ/State admins.

4) Transparency
   - Display signage at godowns indicating CCTV monitoring and purpose.

## Security controls (current)

- Transport
  - MQTT and HTTP operate in trusted networks for PoC.
- Authentication
  - Header-based auth with optional bearer token (`PDS_AUTH_DISABLED=false`).
- Audit trails
  - Alert actions stored in `alert_actions`.
  - After-hours policy changes stored in `after_hours_policy_audit`.
  - Notification deliveries stored in `notification_outbox`.

## Recommended controls for production rollout

- Enable token-based auth and rotate secrets quarterly.
- Enforce TLS for all HTTP and MQTT traffic.
- Store evidence in object storage with signed URLs.
- Enable database encryption at rest.

## Data retention recommendations

PoC (Pethapur):
- Events: 30 to 60 days
- Alerts: 180 days
- Evidence snapshots: 30 to 90 days
- Watchlist match events: 180 days

Production (statewide):
- Align with state policy and legal guidance.

## Watchlist data handling

- Store watchlist images and embeddings with restricted access.
- Do not share watchlist images outside authorized channels.
- Log all watchlist changes and access.

## Incident response and reporting

- Maintain incident logs for fire, intrusion, and blacklist matches.
- Provide weekly summary to HQ.

## Not implemented yet

- Centralized IAM / SSO integration.
- Automated data retention purge jobs.
