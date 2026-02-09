"""
Disk-backed outbox for edge events.

Stores events locally so they can be retried when MQTT/HTTP is unavailable.
"""

from __future__ import annotations

import datetime
import logging
import os
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


def _utcnow_iso() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _read_bool(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y"}


def _read_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _read_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


@dataclass
class OutboxSettings:
    enabled: bool
    db_path: Path
    flush_interval_sec: float
    max_attempts: int
    max_queue: int
    max_payload_bytes: int
    summary_interval_sec: float


def load_outbox_settings() -> OutboxSettings:
    enabled = _read_bool("EDGE_OUTBOX_ENABLED", "true")
    default_path = Path("/opt/app/data/outbox.db")
    configured = os.getenv("EDGE_OUTBOX_DB_PATH")
    if configured:
        db_path = Path(configured)
    else:
        db_path = default_path
    return OutboxSettings(
        enabled=enabled,
        db_path=db_path,
        flush_interval_sec=_read_float("EDGE_OUTBOX_FLUSH_INTERVAL_SEC", 2.0),
        max_attempts=_read_int("EDGE_OUTBOX_MAX_ATTEMPTS", 20),
        max_queue=_read_int("EDGE_OUTBOX_MAX_QUEUE", 50000),
        max_payload_bytes=_read_int("EDGE_OUTBOX_MAX_PAYLOAD_BYTES", 512 * 1024),
        summary_interval_sec=_read_float("EDGE_OUTBOX_SUMMARY_INTERVAL_SEC", 60.0),
    )


class Outbox:
    def __init__(
        self,
        db_path: Path,
        *,
        max_queue: int,
        max_payload_bytes: int,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger("Outbox")
        self.db_path = db_path
        self.max_queue = max(0, int(max_queue))
        self.max_payload_bytes = max(1024, int(max_payload_bytes))
        self._lock = threading.Lock()
        self._conn = self._open_connection(self.db_path)
        self._init_db()

    def _open_connection(self, path: Path) -> sqlite3.Connection:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at_utc TEXT NOT NULL,
                    event_type TEXT,
                    camera_id TEXT,
                    godown_id TEXT,
                    payload_json TEXT NOT NULL,
                    topic TEXT,
                    transport TEXT,
                    http_fallback INTEGER DEFAULT 0,
                    attempts INTEGER DEFAULT 0,
                    next_attempt_at_utc TEXT,
                    last_error TEXT,
                    status TEXT DEFAULT 'pending'
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_outbox_status_next ON outbox(status, next_attempt_at_utc)"
            )
            self._ensure_column("topic", "TEXT")
            self._ensure_column("transport", "TEXT")
            self._ensure_column("http_fallback", "INTEGER DEFAULT 0")

    def _ensure_column(self, name: str, ddl: str) -> None:
        cols = {row["name"] for row in self._conn.execute("PRAGMA table_info(outbox)")}
        if name in cols:
            return
        self._conn.execute(f"ALTER TABLE outbox ADD COLUMN {name} {ddl}")

    def enqueue(
        self,
        *,
        event_type: str,
        camera_id: Optional[str],
        godown_id: Optional[str],
        payload_json: str,
        topic: Optional[str],
        transport: str = "mqtt",
        http_fallback: bool = False,
    ) -> bool:
        payload_bytes = len(payload_json.encode("utf-8"))
        if payload_bytes > self.max_payload_bytes:
            self.logger.warning(
                "Outbox drop: payload too large bytes=%s event_type=%s camera=%s",
                payload_bytes,
                event_type,
                camera_id,
            )
            return False
        created_at = _utcnow_iso()
        with self._lock:
            self._trim_if_needed_locked(extra=1)
            try:
                self._conn.execute(
                    """
                    INSERT INTO outbox (
                        created_at_utc,
                        event_type,
                        camera_id,
                        godown_id,
                        payload_json,
                        topic,
                        transport,
                        http_fallback,
                        attempts,
                        next_attempt_at_utc,
                        last_error,
                        status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NULL, 'pending')
                    """,
                    (
                        created_at,
                        event_type,
                        camera_id,
                        godown_id,
                        payload_json,
                        topic,
                        transport,
                        1 if http_fallback else 0,
                        created_at,
                    ),
                )
                return True
            except Exception as exc:
                self.logger.error(
                    "Outbox enqueue failed event_type=%s camera=%s: %s",
                    event_type,
                    camera_id,
                    exc,
                )
                return False

    def _trim_if_needed_locked(self, extra: int = 0) -> None:
        if self.max_queue <= 0:
            return
        cur = self._conn.execute("SELECT COUNT(*) AS cnt FROM outbox")
        count = int(cur.fetchone()["cnt"])
        if count + extra <= self.max_queue:
            return
        drop = (count + extra) - self.max_queue
        if drop <= 0:
            return
        self._conn.execute(
            "DELETE FROM outbox WHERE id IN (SELECT id FROM outbox ORDER BY id ASC LIMIT ?)",
            (drop,),
        )
        self.logger.warning("Outbox full; dropped %s oldest events", drop)

    def get_due(self, limit: int = 100) -> list[Dict[str, Any]]:
        now = _utcnow_iso()
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT id, event_type, camera_id, godown_id, payload_json, topic, transport,
                       http_fallback, attempts, next_attempt_at_utc, last_error, status
                FROM outbox
                WHERE status = 'pending'
                  AND (next_attempt_at_utc IS NULL OR next_attempt_at_utc <= ?)
                ORDER BY id ASC
                LIMIT ?
                """,
                (now, int(limit)),
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def mark_sent(self, row_id: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE outbox SET status='sent', last_error=NULL WHERE id=?",
                (int(row_id),),
            )

    def mark_failed(
        self,
        row_id: int,
        *,
        attempts: int,
        error: str,
        max_attempts: int,
    ) -> None:
        next_attempt = _utcnow_iso()
        attempts = int(attempts) + 1
        delay = min(60, 2 ** min(attempts, 6))
        next_dt = datetime.datetime.utcnow() + datetime.timedelta(seconds=delay)
        next_attempt = next_dt.replace(microsecond=0).isoformat() + "Z"
        status = "pending"
        if attempts >= max_attempts:
            status = "dead"
        with self._lock:
            self._conn.execute(
                """
                UPDATE outbox
                SET attempts=?, next_attempt_at_utc=?, last_error=?, status=?
                WHERE id=?
                """,
                (attempts, next_attempt, (error or "")[:300], status, int(row_id)),
            )

    def stats(self) -> Dict[str, int]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT status, COUNT(*) AS cnt FROM outbox GROUP BY status"
            )
            rows = cur.fetchall()
        stats = {"pending": 0, "sent": 0, "dead": 0}
        for row in rows:
            status = row["status"]
            if status in stats:
                stats[status] = int(row["cnt"])
        return stats

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass
