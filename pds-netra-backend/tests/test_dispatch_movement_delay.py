import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.vehicle_gate_session import VehicleGateSession
from app.models.event import Alert
from app.schemas.event import EventIn, MetaIn
from app.services.event_ingest import handle_incoming_event
from app.services.vehicle_gate import process_vehicle_gate_sessions


def _make_session():
    os.environ["DISPATCH_MOVEMENT_TIMEZONE"] = "Asia/Kolkata"
    os.environ["DISPATCH_MOVEMENT_THRESHOLDS_HOURS"] = "3,6,9,12,24"
    os.environ["ENABLE_VEHICLE_GATE_WATCHDOG"] = "true"
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()


def _build_event(ts: datetime, direction: str) -> EventIn:
    return EventIn(
        godown_id="GDN_001",
        camera_id="CAM_GATE_1",
        event_id=str(uuid.uuid4()),
        event_type="ANPR_HIT",
        severity="info",
        timestamp_utc=ts,
        bbox=[10, 10, 100, 60],
        track_id=0,
        image_url="http://localhost/snap.jpg",
        clip_url=None,
        meta=MetaIn(
            zone_id=None,
            rule_id=None,
            confidence=0.9,
            movement_type=None,
            plate_text="GJ01AB1234",
            plate_norm="GJ01AB1234",
            direction=direction,
            match_status=None,
            reason=None,
            person_id=None,
            person_name=None,
            person_role=None,
            extra={},
        ),
    )


def test_entry_creates_open_session():
    db = _make_session()
    event_in = _build_event(datetime.now(timezone.utc), "ENTRY")
    handle_incoming_event(event_in, db)
    session = db.query(VehicleGateSession).first()
    assert session is not None
    assert session.status == "OPEN"


def test_exit_closes_session():
    db = _make_session()
    handle_incoming_event(_build_event(datetime.now(timezone.utc) - timedelta(hours=1), "ENTRY"), db)
    handle_incoming_event(_build_event(datetime.now(timezone.utc), "EXIT"), db)
    session = db.query(VehicleGateSession).order_by(VehicleGateSession.entry_at.desc()).first()
    assert session is not None
    assert session.status == "CLOSED"
    assert session.exit_at is not None


def test_reminder_once_at_threshold():
    db = _make_session()
    entry_time = datetime.now(timezone.utc) - timedelta(hours=4)
    handle_incoming_event(_build_event(entry_time, "ENTRY"), db)
    process_vehicle_gate_sessions(db)
    alerts = db.query(Alert).filter(Alert.alert_type == "DISPATCH_MOVEMENT_DELAY").all()
    assert len(alerts) == 1
    process_vehicle_gate_sessions(db)
    alerts2 = db.query(Alert).filter(Alert.alert_type == "DISPATCH_MOVEMENT_DELAY").all()
    assert len(alerts2) == 1
    session = db.query(VehicleGateSession).first()
    assert session is not None
    assert "3" in (session.reminders_sent or {})


def test_no_reminder_after_exit():
    db = _make_session()
    entry_time = datetime.now(timezone.utc) - timedelta(hours=4)
    handle_incoming_event(_build_event(entry_time, "ENTRY"), db)
    handle_incoming_event(_build_event(datetime.now(timezone.utc), "EXIT"), db)
    process_vehicle_gate_sessions(db)
    alerts = db.query(Alert).filter(Alert.alert_type == "DISPATCH_MOVEMENT_DELAY").all()
    assert len(alerts) == 0
