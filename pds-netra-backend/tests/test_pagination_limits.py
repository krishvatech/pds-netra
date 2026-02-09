import os

# Lightweight DB setup and disable background tasks
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:////tmp/pds_netra_test_pagination.db")
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


def _seed_godowns(count: int = 10) -> None:
    with SessionLocal() as db:
        existing = db.query(Godown).count()
        if existing >= count:
            return
        for i in range(existing, count):
            gid = f"GDN_TEST_{i:03d}"
            db.add(Godown(id=gid, name=f"Godown {i}", district="D1"))
        db.commit()


def test_page_size_capped(monkeypatch):
    monkeypatch.setenv("API_MAX_PAGE_SIZE", "5")
    with _client() as client:
        _seed_godowns(12)
        resp = client.get("/api/v1/godowns?page_size=100")
        assert resp.status_code == 200
        assert len(resp.json()) == 5
        assert resp.headers.get("X-Page-Size") == "5"


def test_negative_page_rejected():
    with _client() as client:
        resp = client.get("/api/v1/godowns?page=-1")
        assert resp.status_code == 422
        resp = client.get("/api/v1/godowns?page_size=0")
        assert resp.status_code == 422
