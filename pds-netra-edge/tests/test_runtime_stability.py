import datetime
import threading

from app.config import CameraConfig, Settings, TrackingConfig
from app.cv.pipeline import Pipeline
from app.runtime.camera_loop import CameraHealthState
from app.runtime.scheduler import Scheduler


class _DummyMQTTClient:
    def __init__(self) -> None:
        self._connected = threading.Event()
        self._connected.set()
        self.events = []
        self.health = []

    def publish_event(self, event) -> None:  # type: ignore[no-untyped-def]
        self.events.append(event)

    def publish_health(self, health) -> None:  # type: ignore[no-untyped-def]
        self.health.append(health)


def _settings(camera_id: str = "CAM_1") -> Settings:
    return Settings(
        godown_id="GDN_TEST",
        timezone="Asia/Kolkata",
        cameras=[CameraConfig(id=camera_id, rtsp_url="rtsp://example")],
        rules=[],
        mqtt_broker_host="localhost",
        mqtt_broker_port=1883,
        tracking=TrackingConfig(),
        dispatch_plan_path="data/dispatch_plan.json",
        dispatch_plan_reload_sec=10,
        bag_class_keywords=[],
        bag_movement_px_threshold=50,
        bag_movement_time_window_sec=2,
    )


def test_scheduler_respects_startup_grace_for_no_frame_camera():
    now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    state = CameraHealthState(started_at_utc=now - datetime.timedelta(seconds=5))
    mqtt = _DummyMQTTClient()
    scheduler = Scheduler(_settings(), mqtt, camera_states={"CAM_1": state})
    scheduler.startup_grace_sec = 45

    scheduler._send_health()

    assert state.is_online is True
    assert state.offline_reported is False
    assert len(mqtt.events) == 0
    assert len(mqtt.health) == 1
    assert mqtt.health[0].online_cameras == 1


def test_scheduler_marks_camera_offline_after_grace_expires():
    now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    state = CameraHealthState(started_at_utc=now - datetime.timedelta(seconds=90))
    mqtt = _DummyMQTTClient()
    scheduler = Scheduler(_settings(), mqtt, camera_states={"CAM_1": state})
    scheduler.startup_grace_sec = 30

    scheduler._send_health()

    assert state.is_online is False
    assert state.offline_reported is True
    assert len(mqtt.events) == 1


class _DummyDetector:
    def track(self, _frame):  # type: ignore[no-untyped-def]
        return []


class _DummyCapture:
    def __init__(self, total_frames: int) -> None:
        self._total_frames = total_frames
        self._idx = 0
        self.released = False

    def isOpened(self) -> bool:  # noqa: N802
        return True

    def read(self):  # type: ignore[no-untyped-def]
        if self._idx < self._total_frames:
            frame = {"frame": self._idx}
            self._idx += 1
            return True, frame
        return False, None

    def get(self, _prop):  # type: ignore[no-untyped-def]
        return 15.0

    def release(self) -> None:
        self.released = True


def test_pipeline_file_source_exits_on_eof(monkeypatch):
    processed = []
    capture = _DummyCapture(total_frames=3)
    open_calls = {"count": 0}

    def _open_capture(*, realtime_source: bool):  # type: ignore[no-untyped-def]
        open_calls["count"] += 1
        assert realtime_source is False
        return capture

    def _callback(objects, frame=None, frame_ts=None):  # type: ignore[no-untyped-def]
        processed.append((objects, frame, frame_ts))

    pipeline = Pipeline(
        source="/tmp/test.mp4",
        camera_id="CAM_TEST",
        detector=_DummyDetector(),
        callback=_callback,
    )
    monkeypatch.setattr(pipeline, "_open_capture", _open_capture)

    pipeline.run()

    assert open_calls["count"] == 1
    assert len(processed) == 3
    assert capture.released is True
