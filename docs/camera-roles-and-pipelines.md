# Camera Roles and Pipelines

This guide explains how to route cameras into the correct detection pipelines using roles and per‑camera module flags.

## Roles

Each camera can be assigned a role:

- `GATE_ANPR`: ANPR + gate entry/exit inference only.
- `SECURITY`: Person/animal/fire detection and other security analytics.
- `HEALTH_ONLY`: Health monitoring only (offline, tamper, etc.).

If no role is specified, the edge node preserves **legacy behavior** (all global detections run, including ANPR if enabled).

## Module flags (optional)

You can override defaults per camera using `modules`:

- `anpr_enabled`
- `gate_entry_exit_enabled`
- `person_after_hours_enabled`
- `animal_detection_enabled`
- `fire_detection_enabled`
- `health_monitoring_enabled`

When a role is explicitly set, defaults are applied based on that role and can be overridden by these flags.

## ANPR camera calibration (per camera)

For ANPR cameras, you can provide per‑camera gate calibration and cooldown:

- `gate_line`: `[[x1, y1], [x2, y2]]` or `{x1, y1, x2, y2}`
- `inside_side`: `POSITIVE` or `NEGATIVE`
- `direction_inference`: `LINE_CROSSING` or `SESSION_HEURISTIC`
- `anpr_event_cooldown_seconds`: per‑camera event dedupe (default 10 if set at camera level)

`SESSION_HEURISTIC` disables line‑crossing on the edge and lets the backend infer entry/exit.

## Example config

```yaml
cameras:
  - id: CAM_GATE_1
    role: GATE_ANPR
    rtsp_url: rtsp://example
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

  - id: CAM_AISLE_3
    role: SECURITY
    rtsp_url: rtsp://example
    modules:
      person_after_hours_enabled: true
      animal_detection_enabled: true
      fire_detection_enabled: false
      health_monitoring_enabled: true
```

## Backend behavior

- ANPR gate sessions are only created for cameras with role `GATE_ANPR`.
- For legacy setups without roles, ANPR sessions are still accepted to avoid breaking existing pipelines.

## Migration notes

1. Add `role` to ANPR camera(s) as `GATE_ANPR`.
2. Add `role` to other cameras as `SECURITY`.
3. Optionally add `modules` overrides per camera.
