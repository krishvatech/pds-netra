import json
import logging
from pathlib import Path

from app.core import errors


def test_safe_json_dump_atomic_writes(tmp_path: Path):
    path = tmp_path / "payload.json"
    payload = {"ok": True, "count": 1}
    logger = logging.getLogger("test_errors")

    assert errors.safe_json_dump_atomic(path, payload, logger=logger) is True
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == payload


def test_safe_json_dump_atomic_does_not_corrupt_on_failure(tmp_path: Path, monkeypatch, caplog):
    path = tmp_path / "payload.json"
    path.write_text(json.dumps({"stable": True}), encoding="utf-8")
    logger = logging.getLogger("test_errors")

    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(errors.json, "dump", _boom)
    caplog.set_level(logging.ERROR)

    ok = errors.safe_json_dump_atomic(path, {"new": "data"}, logger=logger)
    assert ok is False

    # File should remain uncorrupted (original content)
    assert json.loads(path.read_text(encoding="utf-8")) == {"stable": True}

    # Verify we logged the failure
    assert any("JSON atomic write failed" in rec.message for rec in caplog.records)
