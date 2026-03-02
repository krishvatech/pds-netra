import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.event import Alert
from app.schemas.event import EventIn, MetaIn
from app.services.event_ingest import handle_incoming_event


def _make_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()


def _build_event(*, zone_id: str, absent_seconds: int, threshold_seconds: int) -> EventIn:
    return EventIn(
        godown_id="GDN_SAMPLE",
        camera_id="CAM_WS_1",
        event_id=str(uuid.uuid4()),
        event_type="WORKSTATION_ABSENCE",
        severity="warning",
        timestamp_utc=datetime.now(timezone.utc),
        bbox=None,
        track_id=None,
        image_url="http://localhost/ws.jpg",
        clip_url=None,
        meta=MetaIn(
            zone_id=zone_id,
            rule_id="WORKSTATION_ABSENCE_MONITOR",
            confidence=1.0,
            movement_type=None,
            plate_text=None,
            plate_norm=None,
            direction=None,
            match_status=None,
            reason=None,
            person_id=None,
            person_name=None,
            person_role=None,
            animal_species=None,
            animal_count=None,
            animal_confidence=None,
            animal_is_night=None,
            animal_bboxes=None,
            fire_classes=None,
            fire_confidence=None,
            fire_bboxes=None,
            fire_model_name=None,
            fire_model_version=None,
            fire_weights_id=None,
            extra={
                "workstation_zone_id": zone_id,
                "absent_seconds": str(absent_seconds),
                "threshold_seconds": str(threshold_seconds),
                "snapshot_url": "http://localhost/ws.jpg",
            },
        ),
    )


def test_station_absence_creates_alert_type_and_summary():
    db = _make_session()
    event_in = _build_event(zone_id="zone_ws_1", absent_seconds=45, threshold_seconds=30)
    handle_incoming_event(event_in, db)

    alert = db.query(Alert).filter(Alert.alert_type == "WORKPLACE_WORKSTATION_ABSENCE").first()
    assert alert is not None
    assert alert.zone_id == "zone_ws_1"
    assert "zone_ws_1" in (alert.summary or "")
    assert "45s" in (alert.summary or "")
    assert "30s" in (alert.summary or "")
