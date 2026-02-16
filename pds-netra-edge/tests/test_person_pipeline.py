import datetime

import numpy as np

from app.cv.person_pipeline import PersonPipeline
from app.cv.pipeline import DetectedObject


def _person(track_id: int, bbox: list[int], confidence: float = 0.9) -> DetectedObject:
    return DetectedObject(
        camera_id="CAM_1",
        class_name="person",
        confidence=confidence,
        bbox=bbox,
        track_id=track_id,
        timestamp_utc="2026-01-01T00:00:00Z",
    )


def test_person_pipeline_disabled_by_default(monkeypatch):
    monkeypatch.delenv("EDGE_PERSON_PIPELINE", raising=False)
    monkeypatch.delenv("EDGE_PERSON_LINE_CROSS_ENABLED", raising=False)
    monkeypatch.delenv("EDGE_PERSON_ROI_EVENTS_ENABLED", raising=False)

    pipeline = PersonPipeline(camera_id="CAM_1", zone_polygons={})
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    objects = [_person(1, [10, 10, 30, 30])]
    merged, signals = pipeline.process(objects=objects, frame=frame, now_utc=datetime.datetime.utcnow())

    assert pipeline.is_enabled() is False
    assert merged == objects
    assert signals == []


def test_line_cross_signal_emitted(monkeypatch):
    monkeypatch.setenv("EDGE_PERSON_PIPELINE", "yolo")
    monkeypatch.setenv("EDGE_PERSON_LINE_CROSS_ENABLED", "true")
    monkeypatch.setenv("EDGE_PERSON_LINE", "0.50,0.00;0.50,1.00")
    monkeypatch.setenv("EDGE_PERSON_LINE_COOLDOWN_SEC", "1")
    monkeypatch.setenv("EDGE_PERSON_LINE_MIN_MOTION_PX", "1")

    pipeline = PersonPipeline(camera_id="CAM_1", zone_polygons={})
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    now = datetime.datetime.utcnow()

    # Left of x=50
    pipeline.process(
        objects=[_person(42, [10, 30, 25, 70])],
        frame=frame,
        now_utc=now,
    )
    # Right of x=50 (cross)
    _, signals = pipeline.process(
        objects=[_person(42, [70, 30, 90, 70])],
        frame=frame,
        now_utc=now + datetime.timedelta(seconds=1),
    )

    assert any(sig.event_type == "PERSON_LINE_CROSS" for sig in signals)


def test_deepstream_mode_falls_back_to_yolo(monkeypatch):
    monkeypatch.setenv("EDGE_PERSON_PIPELINE", "deepstream")
    monkeypatch.delenv("EDGE_PERSON_LINE_CROSS_ENABLED", raising=False)
    monkeypatch.delenv("EDGE_PERSON_ROI_EVENTS_ENABLED", raising=False)

    pipeline = PersonPipeline(camera_id="CAM_1", zone_polygons={})
    frame = np.zeros((120, 120, 3), dtype=np.uint8)
    objects = [_person(7, [20, 20, 50, 80])]
    merged, signals = pipeline.process(objects=objects, frame=frame, now_utc=datetime.datetime.utcnow())

    assert pipeline.mode == "deepstream"
    assert any(obj.track_id == 7 for obj in merged)
    assert signals == []

