import datetime
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.event import Alert
from app.models.notification_endpoint import NotificationEndpoint
from app.models.notification_outbox import NotificationOutbox
from app.services.notification_outbox import enqueue_alert_notifications, enqueue_report_notifications
from app.services.alert_reports import generate_hq_report
from app.services.notification_worker import (
    NotificationProvider,
    ProviderSet,
    process_outbox_batch,
)


def _make_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()


def _create_alert(db) -> Alert:
    alert = Alert(
        godown_id="GDN_SAMPLE",
        camera_id="CAM_1",
        alert_type="FIRE_DETECTED",
        severity_final="critical",
        start_time=datetime.datetime.now(datetime.timezone.utc),
        end_time=None,
        status="OPEN",
        summary="Fire detected",
        zone_id=None,
        extra={"fire_confidence": 0.9},
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def test_enqueue_alert_notifications_idempotent():
    db = _make_session()
    endpoint_hq = NotificationEndpoint(
        scope="HQ",
        godown_id=None,
        channel="EMAIL",
        target="hq@example.com",
        is_enabled=True,
    )
    endpoint_godown = NotificationEndpoint(
        scope="GODOWN_MANAGER",
        godown_id="GDN_SAMPLE",
        channel="WHATSAPP",
        target="+910000000000",
        is_enabled=True,
    )
    db.add(endpoint_hq)
    db.add(endpoint_godown)
    db.commit()
    alert = _create_alert(db)

    created = enqueue_alert_notifications(db, alert)
    assert created == 1
    created_again = enqueue_alert_notifications(db, alert)
    assert created_again == 0
    rows = db.query(NotificationOutbox).all()
    assert len(rows) == 1
    assert rows[0].channel == "WHATSAPP"


def test_enqueue_alert_notifications_combines_env_call_with_endpoints():
    db = _make_session()
    endpoint_email = NotificationEndpoint(
        scope="GODOWN_MANAGER",
        godown_id="GDN_SAMPLE",
        channel="EMAIL",
        target="manager@example.com",
        is_enabled=True,
    )
    db.add(endpoint_email)
    db.commit()

    prev_value = os.environ.get("WATCHLIST_NOTIFY_GODOWN_CALLS")
    try:
        os.environ["WATCHLIST_NOTIFY_GODOWN_CALLS"] = "GDN_SAMPLE:+919876543210"
        alert = _create_alert(db)
        created = enqueue_alert_notifications(db, alert)
        assert created == 2
        rows = db.query(NotificationOutbox).all()
        channels = {row.channel for row in rows}
        assert "EMAIL" in channels
        assert "CALL" in channels
    finally:
        if prev_value is None:
            os.environ.pop("WATCHLIST_NOTIFY_GODOWN_CALLS", None)
        else:
            os.environ["WATCHLIST_NOTIFY_GODOWN_CALLS"] = prev_value


def test_worker_marks_sent_with_log_provider():
    db = _make_session()
    alert = _create_alert(db)
    outbox = NotificationOutbox(
        kind="ALERT",
        alert_id=alert.public_id,
        report_id=None,
        channel="WHATSAPP",
        target="+910000000001",
        subject=None,
        message="Test message",
        media_url=None,
        status="PENDING",
        attempts=0,
    )
    db.add(outbox)
    db.commit()

    class LogProvider(NotificationProvider):
        def send_whatsapp(self, to: str, message: str, media_url=None):
            return "log"

        def send_email(self, to: str, subject: str, html: str):
            return "log"

        def send_call(self, to: str, message: str):
            return "log"

    providers = ProviderSet(whatsapp=LogProvider(), email=LogProvider(), call=LogProvider())
    processed = process_outbox_batch(db, providers=providers, max_attempts=3, batch_size=5)
    assert processed == 1
    row = db.query(NotificationOutbox).first()
    assert row.status == "SENT"
    assert row.sent_at is not None


def test_worker_sends_call_channel():
    db = _make_session()
    alert = _create_alert(db)
    outbox = NotificationOutbox(
        kind="ALERT",
        alert_id=alert.public_id,
        report_id=None,
        channel="CALL",
        target="+910000000002",
        subject=None,
        message="Call message",
        media_url=None,
        status="PENDING",
        attempts=0,
    )
    db.add(outbox)
    db.commit()

    class CallProvider(NotificationProvider):
        def send_whatsapp(self, to: str, message: str, media_url=None):
            raise RuntimeError("unexpected whatsapp")

        def send_email(self, to: str, subject: str, html: str):
            raise RuntimeError("unexpected email")

        def send_call(self, to: str, message: str):
            return "twilio-call-id"

    providers = ProviderSet(
        whatsapp=CallProvider(),
        email=CallProvider(),
        call=CallProvider(),
    )
    processed = process_outbox_batch(db, providers=providers, max_attempts=3, batch_size=5)
    assert processed == 1
    row = db.query(NotificationOutbox).first()
    assert row.status == "SENT"
    assert row.provider_message_id == "twilio-call-id"


def test_worker_retries_on_failure():
    db = _make_session()
    alert = _create_alert(db)
    outbox = NotificationOutbox(
        kind="ALERT",
        alert_id=alert.public_id,
        report_id=None,
        channel="EMAIL",
        target="fail@example.com",
        subject="Test",
        message="<b>fail</b>",
        media_url=None,
        status="PENDING",
        attempts=0,
    )
    db.add(outbox)
    db.commit()

    class FailingProvider(NotificationProvider):
        def send_whatsapp(self, to: str, message: str, media_url=None):
            raise RuntimeError("boom")

        def send_email(self, to: str, subject: str, html: str):
            raise RuntimeError("boom")

        def send_call(self, to: str, message: str):
            raise RuntimeError("boom")

    providers = ProviderSet(whatsapp=FailingProvider(), email=FailingProvider(), call=FailingProvider())
    processed = process_outbox_batch(db, providers=providers, max_attempts=5, batch_size=5)
    assert processed == 1
    row = db.query(NotificationOutbox).first()
    assert row.status == "RETRYING"
    assert row.attempts == 1
    assert row.next_retry_at is not None


def test_hq_report_enqueues_to_hq_only():
    db = _make_session()
    endpoint_hq = NotificationEndpoint(
        scope="HQ",
        godown_id=None,
        channel="EMAIL",
        target="hq@example.com",
        is_enabled=True,
    )
    endpoint_godown = NotificationEndpoint(
        scope="GODOWN_MANAGER",
        godown_id="GDN_SAMPLE",
        channel="WHATSAPP",
        target="+910000000000",
        is_enabled=True,
    )
    db.add(endpoint_hq)
    db.add(endpoint_godown)
    db.commit()

    report = generate_hq_report(db, period="24h", force=True)
    rows = db.query(NotificationOutbox).filter(NotificationOutbox.report_id == report.id).all()
    assert len(rows) == 1
    assert rows[0].channel == "EMAIL"
