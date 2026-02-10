import os
import uuid

# Ensure a lightweight, local DB and no background threads during auth tests.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:////tmp/pds_netra_test_auth.db")
os.environ.setdefault("AUTO_CREATE_DB", "true")
os.environ.setdefault("AUTO_SEED_GODOWNS", "false")
os.environ.setdefault("AUTO_SEED_CAMERAS_FROM_EDGE", "false")
os.environ.setdefault("AUTO_SEED_RULES", "false")
os.environ.setdefault("ENABLE_MQTT_CONSUMER", "false")
os.environ.setdefault("ENABLE_DISPATCH_WATCHDOG", "false")
os.environ.setdefault("ENABLE_DISPATCH_PLAN_SYNC", "false")
os.environ.setdefault("AUTO_SEED_ADMIN_USER", "false")
os.environ.setdefault("PDS_JWT_SECRET", "test-jwt-secret-strong-value-123456")

from fastapi.testclient import TestClient

from app.main import create_app
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.app_user import AppUser
from sqlalchemy import func


def _client() -> TestClient:
    app = create_app()
    return TestClient(app)


def _create_user(*, username: str, password: str, role: str = "STATE_ADMIN") -> None:
    with SessionLocal() as db:
        existing = db.query(AppUser).filter(func.lower(AppUser.username) == username.lower()).first()
        if existing:
            existing.password_hash = hash_password(password)
            existing.role = role
            existing.is_active = True
            db.add(existing)
            db.commit()
            return
        user = AppUser(
            username=username,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()


def test_auth_disabled_allows_protected(monkeypatch):
    monkeypatch.setenv("PDS_AUTH_DISABLED", "true")
    with _client() as client:
        resp = client.get("/api/v1/godowns")
        assert resp.status_code == 200


def test_auth_enabled_blocks_missing_token(monkeypatch):
    monkeypatch.setenv("PDS_AUTH_DISABLED", "false")
    with _client() as client:
        resp = client.get("/api/v1/godowns")
        assert resp.status_code == 401


def test_auth_enabled_allows_valid_token(monkeypatch):
    monkeypatch.setenv("PDS_AUTH_DISABLED", "false")
    with _client() as client:
        _create_user(username="admin", password="admin")
        login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        resp = client.get("/api/v1/godowns", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200


def test_auth_enabled_blocks_invalid_token(monkeypatch):
    monkeypatch.setenv("PDS_AUTH_DISABLED", "false")
    with _client() as client:
        resp = client.get("/api/v1/godowns", headers={"Authorization": "Bearer invalid-token"})
        assert resp.status_code == 401


def test_health_public_in_both_modes(monkeypatch):
    monkeypatch.setenv("PDS_AUTH_DISABLED", "true")
    with _client() as client:
        resp = client.get("/api/v1/health/summary")
        assert resp.status_code == 200
    monkeypatch.setenv("PDS_AUTH_DISABLED", "false")
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
    with _client() as client:
        _create_user(username="demo", password="demo")
        resp = client.post("/api/v1/auth/login", json=payload)
        assert resp.status_code == 200


def test_register_creates_user_and_allows_login(monkeypatch):
    monkeypatch.setenv("PDS_AUTH_DISABLED", "false")
    username = f"newuser_{uuid.uuid4().hex[:8]}"
    password = "newuser123"
    with _client() as client:
        reg = client.post("/api/v1/auth/register", json={"username": username, "password": password})
        assert reg.status_code == 200, reg.text
        assert reg.json()["user"]["username"] == username
        login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        assert login.status_code == 200


def test_register_duplicate_username_blocked(monkeypatch):
    monkeypatch.setenv("PDS_AUTH_DISABLED", "false")
    username = f"dup_{uuid.uuid4().hex[:8]}"
    with _client() as client:
        first = client.post("/api/v1/auth/register", json={"username": username, "password": "dup12345"})
        assert first.status_code == 200, first.text
        second = client.post("/api/v1/auth/register", json={"username": username, "password": "another123"})
        assert second.status_code == 409
