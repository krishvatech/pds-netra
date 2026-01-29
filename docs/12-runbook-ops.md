# 12 - Runbook / Operations

This runbook is written for daily operations at godown and HQ.

## Roles and responsibilities

- Godown Manager
  - Receives real-time alerts
  - Verifies evidence and executes local SOP
  - Records actions in alert actions
- HQ / District Officer
  - Reviews daily digest
  - Audits trends and compliance
  - Coordinates escalations
- Technical Operator
  - Maintains edge node, backend, and dashboard
  - Monitors worker and MQTT health

## Daily health checks (start of day)

1) Backend API is reachable
   - Expected: `uvicorn` running and responding
2) Notification worker is running
   - `python -m app.worker`
3) MQTT broker reachable on port 1883
4) Dashboard accessible on port 3000
5) Camera online count is stable in dashboard health view

## Incident SOPs

### Fire detection

1) Verify evidence snapshot on alert detail.
2) Call godown security and local fire response team.
3) Evacuate per SOP and inform HQ.
4) Record action in alert actions with timestamp and outcome.

### After-hours person/vehicle

1) Verify alert and evidence.
2) Call security guard on site.
3) If verified intrusion, inform local police station.
4) Record action and outcome in alert actions.

### Blacklist (watchlist) match

1) Verify face snapshot and match score.
2) Alert security team and local enforcement.
3) Notify HQ if match is confirmed.
4) Record action in alert actions.

### Camera offline or tamper

1) Check RTSP stream and camera power.
2) Inspect network switch or PoE injector.
3) If unresolved within 30 minutes, escalate to maintenance vendor.

## Notification failure SOP

1) Open alert detail and check delivery status.
2) If status is FAILED or RETRYING:
   - Verify provider credentials in backend `.env`.
   - Check worker logs for provider errors.
   - Confirm internet connectivity at backend.
3) If still failing after 60 minutes, switch provider to log mode and continue alerting via phone.

## Dispatch movement delay SOP

1) Open Dispatch Movement page.
2) Identify open sessions beyond threshold.
3) Notify dispatch team to verify vehicle status.
4) Record action for each open session.

## Evidence handling

- Evidence snapshots are stored under `pds-netra-backend/data/snapshots`.
- Evidence should be shared only with authorized officials.
- Do not delete evidence until retention policy is met.

## Monitoring and logs

- Edge logs: `pds-netra-edge` runtime output.
- Backend logs: `uvicorn` output.
- Worker logs: `app.worker` output.
- MQTT logs: broker service logs (if using docker-compose).

## Escalation matrix

- Fire detection: immediate escalation to local fire station + HQ.
- Blacklist match: inform security and district officer.
- After-hours intrusion: local security + local police if confirmed.
- Camera tamper: maintenance vendor + district IT.

## Backup and recovery (basic)

- Postgres backup daily (logical dump or snapshot).
- Evidence snapshots backed up weekly or per policy.
- Store backups in a separate secure location.

## Not implemented yet

- Automated ticketing integration for incidents.
