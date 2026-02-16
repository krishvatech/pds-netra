import os
import tempfile
from pathlib import Path

DB_PATH = Path(tempfile.gettempdir()) / "pds_netra_test_face_index_auth.db"
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{DB_PATH}")
os.environ.setdefault("AUTO_CREATE_DB", "true")
os.environ.setdefault("AUTO_SEED_GODOWNS", "false")
os.environ.setdefault("AUTO_SEED_CAMERAS_FROM_EDGE", "false")
os.environ.setdefault("AUTO_SEED_RULES", "false")
os.environ.setdefault("AUTO_SEED_ADMIN_USER", "false")
os.environ.setdefault("ENABLE_MQTT_CONSUMER", "false")
os.environ.setdefault("ENABLE_DISPATCH_WATCHDOG", "false")
os.environ.setdefault("ENABLE_DISPATCH_PLAN_SYNC", "false")
os.environ.setdefault("PDS_AUTH_DISABLED", "false")
os.environ.setdefault("PDS_JWT_SECRET", "test-jwt-secret-strong-value-123456")

from fastapi.testclient import TestClient

from app.main import create_app
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.app_user import AppUser
from app.models.authorized_user import AuthorizedUser
from app.models.godown import Godown


def _client() -> TestClient:
    app = create_app()
    return TestClient(app)


def _seed_face_index_rows() -> None:
    with SessionLocal() as db:
        if not db.get(Godown, "GDN_001"):
            db.add(Godown(id="GDN_001", name="Central"))
        if not db.get(AuthorizedUser, "P1"):
            db.add(
                AuthorizedUser(
                    person_id="P1",
                    name="Person One",
                    role="staff",
                    godown_id="GDN_001",
                    is_active=True,
                    embedding=[0.1, 0.2, 0.3],
                )
            )
        db.commit()


def _create_admin_user() -> None:
    with SessionLocal() as db:
        existing = db.query(AppUser).filter(AppUser.username == "admin").first()
        if existing:
            existing.password_hash = hash_password("admin")
            existing.role = "STATE_ADMIN"
            existing.is_active = True
            db.add(existing)
            db.commit()
            return
        db.add(
            AppUser(
                username="admin",
                password_hash=hash_password("admin"),
                role="STATE_ADMIN",
                is_active=True,
            )
        )
        db.commit()


def _login_token(client: TestClient) -> str:
    _create_admin_user()
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_face_index_requires_auth(monkeypatch) -> None:
    monkeypatch.setenv("PDS_AUTH_DISABLED", "false")
    monkeypatch.setenv("EDGE_BACKEND_TOKEN", "edge-service-token-123")
    _seed_face_index_rows()
    with _client() as client:
        resp = client.get("/api/v1/authorized-users/face-index?godown_id=GDN_001")
        assert resp.status_code == 401


def test_face_index_allows_dashboard_auth(monkeypatch) -> None:
    monkeypatch.setenv("PDS_AUTH_DISABLED", "false")
    monkeypatch.delenv("AUTHORIZED_USERS_SERVICE_TOKEN", raising=False)
    monkeypatch.setenv("EDGE_BACKEND_TOKEN", "edge-service-token-123")
    _seed_face_index_rows()
    with _client() as client:
        token = _login_token(client)
        resp = client.get(
            "/api/v1/authorized-users/face-index?godown_id=GDN_001",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["person_id"] == "P1"


def test_face_index_allows_service_token(monkeypatch) -> None:
    monkeypatch.setenv("PDS_AUTH_DISABLED", "false")
    monkeypatch.delenv("AUTHORIZED_USERS_SERVICE_TOKEN", raising=False)
    monkeypatch.setenv("EDGE_BACKEND_TOKEN", "edge-service-token-123")
    _seed_face_index_rows()
    with _client() as client:
        resp = client.get(
            "/api/v1/authorized-users/face-index?godown_id=GDN_001",
            headers={"Authorization": "Bearer edge-service-token-123"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body) == 1
        assert body[0]["person_id"] == "P1"


def test_face_index_blocks_wrong_service_token(monkeypatch) -> None:
    monkeypatch.setenv("PDS_AUTH_DISABLED", "false")
    monkeypatch.setenv("AUTHORIZED_USERS_SERVICE_TOKEN", "authorized-users-service-token")
    monkeypatch.setenv("EDGE_BACKEND_TOKEN", "legacy-edge-token")
    _seed_face_index_rows()
    with _client() as client:
        resp = client.get(
            "/api/v1/authorized-users/face-index?godown_id=GDN_001",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 403
        assert "service token" in resp.json().get("detail", "").lower()
