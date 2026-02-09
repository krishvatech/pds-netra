from __future__ import annotations

from pathlib import Path

from app.events.outbox import Outbox


def test_outbox_enqueue_and_mark_sent(tmp_path: Path) -> None:
    db_path = tmp_path / "outbox.db"
    outbox = Outbox(db_path, max_queue=10, max_payload_bytes=1024)
    assert outbox.stats()["pending"] == 0

    payload = {"event_id": "evt-1", "event_type": "TEST_EVENT", "camera_id": "CAM_1", "godown_id": "GDN_1"}
    ok = outbox.enqueue(payload, transport_hint="mqtt")
    assert ok
    stats = outbox.stats()
    assert stats["pending"] == 1

    due = outbox.dequeue_batch(limit=10)
    assert len(due) == 1
    row = due[0]
    assert row["event_type"] == "TEST_EVENT"

    outbox.mark_sent(row["id"])
    stats = outbox.stats()
    assert stats["pending"] == 0
    assert stats["sent"] == 1
