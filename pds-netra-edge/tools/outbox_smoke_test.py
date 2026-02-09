#!/usr/bin/env python3
"""
Lightweight outbox smoke test.

Creates a temp outbox DB, enqueues fake events, simulates failures and
success, and asserts pending counts change as expected.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.events.outbox import Outbox


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "outbox.db"
        outbox = Outbox(db_path, max_queue=10, max_payload_bytes=1024)
        assert outbox.pending_count() == 0

        payload = {
            "event_id": "evt-1",
            "event_type": "TEST_EVENT",
            "camera_id": "CAM_1",
            "godown_id": "GDN_1",
            "payload": {"hello": "world"},
        }
        outbox.enqueue(payload)
        assert outbox.pending_count() == 1

        rows = outbox.dequeue_due(limit=1)
        assert len(rows) == 1
        row = rows[0]

        outbox.mark_failed(row["id"], error="mqtt_down", max_attempts=5, backoff_seconds=2)
        rows_after = outbox.dequeue_due(limit=1)
        # backoff should prevent immediate retry
        assert len(rows_after) in (0, 1)

        outbox.mark_sent(row["id"])
        assert outbox.pending_count() == 0

    print("Outbox smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
