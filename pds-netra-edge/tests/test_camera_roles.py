import textwrap

from app.config import (
    CameraConfig,
    CameraModules,
    Settings,
    TrackingConfig,
    AnprConfig,
    AfterHoursPresenceConfig,
    FireDetectionConfig,
    load_settings,
)
from app.runtime.pipeline_router import resolve_camera_modules


def _settings() -> Settings:
    return Settings(
        godown_id="GDN_TEST",
        timezone="Asia/Kolkata",
        cameras=[],
        rules=[],
        mqtt_broker_host="localhost",
        mqtt_broker_port=1883,
        tracking=TrackingConfig(),
        dispatch_plan_path="data/dispatch_plan.json",
        dispatch_plan_reload_sec=10,
        bag_class_keywords=[],
        bag_movement_px_threshold=50,
        bag_movement_time_window_sec=2,
        anpr=AnprConfig(enabled=True),
        watchlist=None,
        after_hours_presence=AfterHoursPresenceConfig(enabled=True),
        fire_detection=FireDetectionConfig(enabled=True),
    )


def test_gate_anpr_defaults():
    settings = _settings()
    camera = CameraConfig(id="CAM_GATE", rtsp_url="rtsp://example", role="GATE_ANPR", role_explicit=True)
    modules = resolve_camera_modules(camera, settings)
    assert modules.anpr_enabled is True
    assert modules.gate_entry_exit_enabled is True
    assert modules.person_after_hours_enabled is False
    assert modules.animal_detection_enabled is False
    assert modules.fire_detection_enabled is False
    assert modules.health_monitoring_enabled is True


def test_gate_anpr_honored_even_when_role_not_explicit():
    settings = _settings()
    camera = CameraConfig(id="CAM_GATE", rtsp_url="rtsp://example", role="GATE_ANPR", role_explicit=False)
    modules = resolve_camera_modules(camera, settings)
    assert modules.anpr_enabled is True
    assert modules.gate_entry_exit_enabled is True
    assert modules.person_after_hours_enabled is False
    assert modules.animal_detection_enabled is False
    assert modules.fire_detection_enabled is False
    assert modules.health_monitoring_enabled is True


def test_gate_anpr_role_guardrail_blocks_heavy_overrides():
    settings = _settings()
    camera = CameraConfig(
        id="CAM_GATE",
        rtsp_url="rtsp://example",
        role="GATE_ANPR",
        role_explicit=True,
        modules=CameraModules(
            person_after_hours_enabled=True,
            animal_detection_enabled=True,
            fire_detection_enabled=True,
        ),
    )
    modules = resolve_camera_modules(camera, settings)
    assert modules.anpr_enabled is True
    assert modules.gate_entry_exit_enabled is True
    assert modules.person_after_hours_enabled is False
    assert modules.animal_detection_enabled is False
    assert modules.fire_detection_enabled is False
    assert modules.health_monitoring_enabled is True


def test_security_defaults_disable_anpr():
    settings = _settings()
    camera = CameraConfig(id="CAM_SEC", rtsp_url="rtsp://example", role="SECURITY", role_explicit=True)
    modules = resolve_camera_modules(camera, settings)
    assert modules.anpr_enabled is False
    assert modules.gate_entry_exit_enabled is False
    assert modules.person_after_hours_enabled is True
    assert modules.animal_detection_enabled is True


def test_legacy_defaults_keep_anpr():
    settings = _settings()
    camera = CameraConfig(id="CAM_LEGACY", rtsp_url="rtsp://example", role="SECURITY", role_explicit=False)
    modules = resolve_camera_modules(camera, settings)
    assert modules.anpr_enabled is True
    assert modules.gate_entry_exit_enabled is True


def test_module_override_enables_anpr():
    settings = _settings()
    camera = CameraConfig(
        id="CAM_OVERRIDE",
        rtsp_url="rtsp://example",
        role="SECURITY",
        role_explicit=True,
        modules=CameraModules(anpr_enabled=True),
    )
    modules = resolve_camera_modules(camera, settings)
    assert modules.anpr_enabled is True


def test_camera_anpr_overrides_parse(tmp_path):
    config_text = textwrap.dedent(
        """
        godown_id: GDN_SAMPLE
        timezone: Asia/Kolkata
        mqtt:
          host: 127.0.0.1
          port: 1883
        cameras:
          - id: CAM_GATE_1
            rtsp_url: rtsp://example
            role: GATE_ANPR
            anpr:
              gate_line:
                x1: 10
                y1: 20
                x2: 30
                y2: 40
              inside_side: negative
              direction_inference: session_heuristic
              anpr_event_cooldown_seconds: 12
        rules: []
        """
    ).strip()
    path = tmp_path / "config.yaml"
    path.write_text(config_text, encoding="utf-8")
    settings = load_settings(str(path))
    assert settings.cameras[0].anpr is not None
    assert settings.cameras[0].anpr.gate_line == [[10, 20], [30, 40]]
    assert settings.cameras[0].anpr.inside_side == "NEGATIVE"
    assert settings.cameras[0].anpr.direction_inference == "SESSION_HEURISTIC"
    assert settings.cameras[0].anpr.anpr_event_cooldown_seconds == 12
