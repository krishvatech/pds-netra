# 11 - PoC Execution Plan (3 months)

## Phase 1 (Weeks 1-4): Setup & Calibration

- Deploy edge node at Pethapur Godown.
- Configure camera roles:
  - Gate camera -> `GATE_ANPR`
  - Others -> `SECURITY`
- Calibrate gate line for ANPR.
- Validate RTSP stability and bandwidth.
- Confirm MQTT connectivity with backend.

## Phase 2 (Weeks 5-8): Detection & Alerts

- Enable after-hours detection and validate timings.
- Enable animal intrusion with night severity tuning.
- Enable fire detection with multi-frame confirm.
- Configure watchlist (blacklist) workflows.
- Confirm alerts and evidence snapshots.

## Phase 3 (Weeks 9-12): Operations & Reporting

- Start HQ daily digest schedule.
- Validate dispatch movement delay thresholds.
- Tune cooldowns and alert dedupe.
- Conduct training for Godown Managers and HQ.

## KPIs / acceptance criteria

- **Alert latency**: < 30 seconds from detection to delivery.
- **False positives**: < 5% for fire and watchlist.
- **ANPR session accuracy**: > 95% correct entry/exit.
- **Operational uptime**: > 95% (camera online status).

## Responsibilities

- **Department**: network readiness, access approvals, SOPs.
- **Startup/System integrator**: edge setup, calibration, dashboards, support.

## Calibration checklist

- Verify `role` and `modules` per camera.
- Set ANPR `gate_line` and `inside_side`.
- Validate after-hours schedule (19:00-06:00).
- Check snapshot evidence URLs load on dashboard.
