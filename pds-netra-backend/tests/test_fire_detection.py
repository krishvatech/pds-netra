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


def _build_event(event_id: str) -> EventIn:
    return EventIn(
        godown_id="GDN_001",
        camera_id="CAM_FIRE_1",
        event_id=event_id,
        event_type="FIRE_DETECTED",
        severity="critical",
        timestamp_utc=datetime.now(timezone.utc),
        bbox=[10, 10, 80, 80],
        track_id=0,
        image_url="http://localhost/fire.jpg",
        clip_url=None,
        meta=MetaIn(
            zone_id=None,
            rule_id="FIRE_DETECTED",
            confidence=0.9,
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
            fire_classes=["fire"],
            fire_confidence=0.9,
            fire_bboxes=[[10, 10, 80, 80]],
            fire_model_name="yolo26",
            fire_model_version=None,
            fire_weights_id="fire.pt",
            extra={},
        ),
    )


def test_fire_detected_creates_alert():
    db = _make_session()
    event_in = _build_event(str(uuid.uuid4()))
    handle_incoming_event(event_in, db)
    alerts = db.query(Alert).filter(Alert.alert_type == "FIRE_DETECTED").all()
    assert len(alerts) == 1
    assert alerts[0].status == "OPEN"


def test_fire_detected_idempotent_event_id():
    db = _make_session()
    event_id = str(uuid.uuid4())
    event_in = _build_event(event_id)
    handle_incoming_event(event_in, db)
    handle_incoming_event(event_in, db)
    alerts = db.query(Alert).filter(Alert.alert_type == "FIRE_DETECTED").all()
    assert len(alerts) == 1


def test_fire_detected_dedup_open_alert():
    db = _make_session()
    handle_incoming_event(_build_event(str(uuid.uuid4())), db)
    handle_incoming_event(_build_event(str(uuid.uuid4())), db)
    alerts = db.query(Alert).filter(Alert.alert_type == "FIRE_DETECTED").all()
    assert len(alerts) == 1
