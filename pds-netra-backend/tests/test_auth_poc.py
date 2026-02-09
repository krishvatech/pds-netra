import os

# Ensure a lightweight, local DB and no background threads during auth tests.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:////tmp/pds_netra_test_auth.db")
os.environ.setdefault("AUTO_CREATE_DB", "true")
os.environ.setdefault("AUTO_SEED_GODOWNS", "false")
os.environ.setdefault("AUTO_SEED_CAMERAS_FROM_EDGE", "false")
os.environ.setdefault("AUTO_SEED_RULES", "false")
os.environ.setdefault("ENABLE_MQTT_CONSUMER", "false")
os.environ.setdefault("ENABLE_DISPATCH_WATCHDOG", "false")
os.environ.setdefault("ENABLE_DISPATCH_PLAN_SYNC", "false")

from fastapi.testclient import TestClient

from app.main import create_app


def _client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_auth_disabled_allows_protected(monkeypatch):
    monkeypatch.setenv("PDS_AUTH_DISABLED", "true")
    with _client() as client:
        resp = client.get("/api/v1/godowns")
        assert resp.status_code == 200


def test_auth_enabled_blocks_missing_token(monkeypatch):
    monkeypatch.setenv("PDS_AUTH_DISABLED", "false")
    monkeypatch.setenv("PDS_AUTH_TOKEN", "test-token")
    with _client() as client:
        resp = client.get("/api/v1/godowns")
        assert resp.status_code == 401


def test_auth_enabled_allows_valid_token(monkeypatch):
    monkeypatch.setenv("PDS_AUTH_DISABLED", "false")
    monkeypatch.setenv("PDS_AUTH_TOKEN", "test-token")
    with _client() as client:
        resp = client.get("/api/v1/godowns", headers={"Authorization": "Bearer test-token"})
        assert resp.status_code == 200


def test_health_public_in_both_modes(monkeypatch):
    monkeypatch.setenv("PDS_AUTH_DISABLED", "true")
    with _client() as client:
        resp = client.get("/api/v1/health/summary")
        assert resp.status_code == 200
    monkeypatch.setenv("PDS_AUTH_DISABLED", "false")
    monkeypatch.setenv("PDS_AUTH_TOKEN", "test-token")
    with _client() as client:
        resp = client.get("/api/v1/health/summary")
        assert resp.status_code == 200


def test_login_public_in_both_modes(monkeypatch):
    payload = {"username": "demo", "password": "demo"}

    monkeypatch.setenv("PDS_AUTH_DISABLED", "true")
    with _client() as client:
        resp = client.post("/api/v1/auth/login", json=payload)
        assert resp.status_code == 200

    monkeypatch.setenv("PDS_AUTH_DISABLED", "false")
    monkeypatch.setenv("PDS_AUTH_TOKEN", "test-token")
    with _client() as client:
        resp = client.post("/api/v1/auth/login", json=payload)
        assert resp.status_code == 200
