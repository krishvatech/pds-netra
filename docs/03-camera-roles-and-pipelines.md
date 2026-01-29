# 03 - Camera Roles and Pipelines

## Roles

- **GATE_ANPR**
  - Runs: ANPR detection + gate entry/exit inference.
  - Does **not** run: person/animal/fire detectors unless explicitly enabled in modules.

- **SECURITY**
  - Runs: after-hours person/vehicle presence, animal intrusion, fire detection, health monitoring.
  - ANPR is **off by default** for role-based configs.

- **HEALTH_ONLY**
  - Runs: camera health/tamper monitoring only.

## Backward compatibility

If a camera **does not specify a role**, the edge node preserves legacy behavior:
- All global detections remain enabled (including ANPR if `anpr.enabled: true`).

This prevents breaking existing deployments.

## Config structure (edge)

File: `pds-netra-edge/config/pds_netra_config.yaml`

### Example: GATE_ANPR camera

```yaml
cameras:
  - id: CAM_GATE_1
    role: GATE_ANPR
    rtsp_url: rtsp://user:pass@ip:554/stream1
    modules:
      anpr_enabled: true
      gate_entry_exit_enabled: true
      person_after_hours_enabled: false
      animal_detection_enabled: false
      fire_detection_enabled: false
      health_monitoring_enabled: true
    anpr:
      gate_line:
        - [960, 0]
        - [960, 1080]
      inside_side: POSITIVE
      direction_inference: LINE_CROSSING
      anpr_event_cooldown_seconds: 10
```

### Example: SECURITY camera

```yaml
  - id: CAM_AISLE_3
    role: SECURITY
    rtsp_url: rtsp://user:pass@ip:554/stream1
    modules:
      anpr_enabled: false
      gate_entry_exit_enabled: false
      person_after_hours_enabled: true
      animal_detection_enabled: true
      fire_detection_enabled: true
      health_monitoring_enabled: true
```

### Example: HEALTH_ONLY camera

```yaml
  - id: CAM_HEALTH_1
    role: HEALTH_ONLY
    rtsp_url: rtsp://user:pass@ip:554/stream1
    modules:
      health_monitoring_enabled: true
```

## Gate line calibration

- **gate_line:** two points that define a virtual line.
- **inside_side:** which side is \"inside\" the godown (POSITIVE or NEGATIVE).
- **direction_inference:**
  - `LINE_CROSSING` (edge determines ENTRY/EXIT)
  - `SESSION_HEURISTIC` (backend infers entry/exit based on open sessions)

### Direction inference behavior

- **LINE_CROSSING**: uses object movement across the gate line.
- **SESSION_HEURISTIC**: if no open session, treat as ENTRY; if open session exists, treat as EXIT (backend fallback).

## Failure modes and fallbacks

- **ANPR gate line missing**: direction becomes `UNKNOWN` and backend may use session heuristic.
- **Fire model missing**: fire detection disables itself safely.
- **Role not set**: legacy behavior preserved (no break).

## Pipeline summary

| Role | ANPR | After-hours | Animals | Fire | Health |
|------|------|-------------|---------|------|--------|
| GATE_ANPR | Yes | No | No | No | Yes |
| SECURITY | No (default) | Yes | Yes | Yes | Yes |
| HEALTH_ONLY | No | No | No | No | Yes |
