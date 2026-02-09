import os

# Lightweight DB setup and disable background tasks
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:////tmp/pds_netra_test_rate_limit.db")
os.environ.setdefault("AUTO_CREATE_DB", "true")
os.environ.setdefault("AUTO_SEED_GODOWNS", "false")
os.environ.setdefault("AUTO_SEED_CAMERAS_FROM_EDGE", "false")
os.environ.setdefault("AUTO_SEED_RULES", "false")
os.environ.setdefault("ENABLE_MQTT_CONSUMER", "false")
os.environ.setdefault("ENABLE_DISPATCH_WATCHDOG", "false")
os.environ.setdefault("ENABLE_DISPATCH_PLAN_SYNC", "false")
os.environ.setdefault("PDS_AUTH_DISABLED", "true")

from fastapi.testclient import TestClient

from app.main import create_app
from app.core.db import SessionLocal
from app.models.godown import Godown


def _client() -> TestClient:
    app = create_app()
    return TestClient(app)


def _seed_godowns(count: int = 1) -> None:
    with SessionLocal() as db:
        existing = db.query(Godown).count()
        if existing >= count:
            return
        for i in range(existing, count):
            gid = f"GDN_RL_{i:03d}"
            db.add(Godown(id=gid, name=f"Godown {i}", district="D1"))
        db.commit()


def test_rate_limit_blocks(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_RPS", "0.1")
    monkeypatch.setenv("RATE_LIMIT_BURST", "1")

    headers = {"Authorization": "Bearer rate-limit-test-token"}
    with _client() as client:
        _seed_godowns(1)
        resp1 = client.get("/api/v1/godowns", headers=headers)
        resp2 = client.get("/api/v1/godowns", headers=headers)
        assert resp1.status_code == 200
        assert resp2.status_code == 429
