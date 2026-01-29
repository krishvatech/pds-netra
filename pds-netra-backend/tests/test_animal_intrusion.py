import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.event import Alert
from app.schemas.event import EventIn, MetaIn
from app.services.event_ingest import handle_incoming_event


def _make_session():
    os.environ["ANIMAL_TIMEZONE"] = "Asia/Kolkata"
    os.environ["ANIMAL_NIGHT_START"] = "19:00"
    os.environ["ANIMAL_NIGHT_END"] = "06:00"
    os.environ["ANIMAL_ALERT_COOLDOWN_SEC"] = "300"
    os.environ["ANIMAL_DAY_SEVERITY"] = "warning"
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()


def _build_event(ts: datetime, species: str) -> EventIn:
    return EventIn(
        godown_id="GDN_001",
        camera_id="CAM_1",
        event_id=str(uuid.uuid4()),
        event_type="ANIMAL_INTRUSION",
        severity="warning",
        timestamp_utc=ts,
        bbox=[10, 10, 100, 100],
        track_id=1,
        image_url="http://localhost/snap.jpg",
        clip_url=None,
        meta=MetaIn(
            zone_id="zone_a",
            rule_id=None,
            confidence=0.82,
            movement_type=None,
            plate_text=None,
            match_status=None,
            reason=None,
            person_id=None,
            person_name=None,
            person_role=None,
            animal_species=species,
            animal_count=1,
            animal_confidence=0.82,
            animal_is_night=None,
            animal_bboxes=[[10, 10, 100, 100]],
            extra={},
        ),
    )


def test_animal_intrusion_night_severity():
    db = _make_session()
    night_ts = datetime(2026, 1, 1, 14, 30, tzinfo=ZoneInfo("UTC"))  # 20:00 IST
    event_in = _build_event(night_ts, "cow")
    handle_incoming_event(event_in, db)
    alert = db.query(Alert).first()
    assert alert is not None
    assert alert.severity_final == "critical"


def test_animal_intrusion_day_severity():
    db = _make_session()
    day_ts = datetime(2026, 1, 1, 4, 30, tzinfo=ZoneInfo("UTC"))  # 10:00 IST
    event_in = _build_event(day_ts, "dog")
    handle_incoming_event(event_in, db)
    alert = db.query(Alert).first()
    assert alert is not None
    assert alert.severity_final == "warning"


def test_animal_intrusion_dedup_per_species():
    db = _make_session()
    ts = datetime(2026, 1, 1, 14, 30, tzinfo=ZoneInfo("UTC"))
    handle_incoming_event(_build_event(ts, "dog"), db)
    handle_incoming_event(_build_event(ts, "dog"), db)
    assert db.query(Alert).count() == 1
    handle_incoming_event(_build_event(ts, "cow"), db)
    assert db.query(Alert).count() == 2
