from datetime import datetime
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.event import Alert
from app.schemas.watchlist import FaceMatchCandidate, FaceMatchEvidence, FaceMatchEventIn, FaceMatchPayload, WatchlistEmbeddingIn
from app.services import watchlist as watchlist_service


def _make_session():
    os.environ["ENABLE_WATCHLIST_MQTT_SYNC"] = "false"
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()


def test_watchlist_crud():
    db = _make_session()
    person = watchlist_service.create_person(db, name="Test Person", alias="Alias", reason="Theft", notes="PoC")
    assert person.id
    assert person.status == "ACTIVE"

    person = watchlist_service.update_person(db, person, {"alias": "Alias2"})
    assert person.alias == "Alias2"

    person = watchlist_service.deactivate_person(db, person)
    assert person.status == "INACTIVE"


def test_face_match_idempotency_and_alert():
    db = _make_session()
    person = watchlist_service.create_person(db, name="Suspect", alias=None, reason="Theft", notes=None)
    watchlist_service.add_embeddings(
        db,
        person=person,
        embeddings=[WatchlistEmbeddingIn(embedding=[0.1] * 512, embedding_version="v1")],
    )

    event_payload = FaceMatchEventIn(
        event_id="evt-1",
        occurred_at=datetime.utcnow(),
        godown_id="GDN_SAMPLE",
        camera_id="CAM_1",
        payload=FaceMatchPayload(
            person_candidate=FaceMatchCandidate(
                embedding_hash="hash",
                match_score=0.85,
                is_blacklisted=True,
                blacklist_person_id=person.id,
            ),
            evidence=FaceMatchEvidence(
                snapshot_url="http://localhost/snap.jpg",
                local_snapshot_path=None,
                bbox=[10, 10, 40, 40],
                frame_ts=datetime.utcnow().isoformat() + "Z",
            ),
        ),
    )

    _, created = watchlist_service.ingest_face_match_event(db, event_payload)
    assert created is True
    _, created2 = watchlist_service.ingest_face_match_event(db, event_payload)
    assert created2 is False

    alerts = db.query(Alert).filter(Alert.alert_type == "BLACKLIST_PERSON_MATCH").all()
    assert len(alerts) == 1
    assert alerts[0].status == "OPEN"
