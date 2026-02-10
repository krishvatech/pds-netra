import os
from pathlib import Path
import tempfile

# Ensure isolated lightweight DB and no background workers.
DB_PATH = Path(tempfile.gettempdir()) / "pds_netra_test_auth_scope.db"
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
from app.services.test_runs import create_test_run


def _client() -> TestClient:
    app = create_app()
    return TestClient(app)


def _create_user(*, username: str, password: str, role: str) -> AppUser:
    with SessionLocal() as db:
        user = AppUser(
            username=username,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def _login_token(client: TestClient, username: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_admin_sees_all_user_sees_only_owned_godowns() -> None:
    with _client() as client:
        _create_user(username="admin", password="admin-pass", role="STATE_ADMIN")
        user_a = _create_user(username="alice", password="alice-pass", role="USER")
        user_b = _create_user(username="bob", password="bob-pass", role="USER")

        admin_token = _login_token(client, "admin", "admin-pass")
        alice_token = _login_token(client, "alice", "alice-pass")
        bob_token = _login_token(client, "bob", "bob-pass")

        resp = client.post(
            "/api/v1/godowns",
            json={"godown_id": "GDN_A", "name": "Alice Godown"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert resp.status_code == 201, resp.text

        resp = client.post(
            "/api/v1/godowns",
            json={"godown_id": "GDN_B", "name": "Bob Godown"},
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert resp.status_code == 201, resp.text

        # Admin can list all.
        resp = client.get("/api/v1/godowns", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        ids = {item["godown_id"] for item in resp.json()}
        assert ids == {"GDN_A", "GDN_B"}

        # Alice can list only owned godowns.
        resp = client.get("/api/v1/godowns", headers={"Authorization": f"Bearer {alice_token}"})
        assert resp.status_code == 200
        ids = {item["godown_id"] for item in resp.json()}
        assert ids == {"GDN_A"}

        # Ownership persisted.
        with SessionLocal() as db:
            from app.models.godown import Godown

            a = db.get(Godown, "GDN_A")
            assert a is not None
            assert a.created_by_user_id == user_a.id
            b = db.get(Godown, "GDN_B")
            assert b is not None
            assert b.created_by_user_id == user_b.id


def test_user_cannot_access_update_delete_other_users_godown() -> None:
    with _client() as client:
        _create_user(username="admin2", password="admin-pass", role="STATE_ADMIN")
        _create_user(username="owner", password="owner-pass", role="USER")
        _create_user(username="other", password="other-pass", role="USER")

        owner_token = _login_token(client, "owner", "owner-pass")
        other_token = _login_token(client, "other", "other-pass")

        create = client.post(
            "/api/v1/godowns",
            json={"godown_id": "GDN_OWNED", "name": "Owned"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert create.status_code == 201, create.text

        detail = client.get(
            "/api/v1/godowns/GDN_OWNED",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert detail.status_code == 403

        update = client.put(
            "/api/v1/godowns/GDN_OWNED",
            json={"name": "Hacked"},
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert update.status_code == 403

        delete = client.delete(
            "/api/v1/godowns/GDN_OWNED",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert delete.status_code == 403


def test_user_only_sees_own_test_runs() -> None:
    with _client() as client:
        _create_user(username="admin3", password="admin-pass", role="STATE_ADMIN")
        _create_user(username="run_owner", password="owner-pass", role="USER")
        _create_user(username="run_other", password="other-pass", role="USER")

        owner_token = _login_token(client, "run_owner", "owner-pass")
        other_token = _login_token(client, "run_other", "other-pass")

        create_owner_g = client.post(
            "/api/v1/godowns",
            json={"godown_id": "GDN_RUN_OWNER", "name": "Owner Godown"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert create_owner_g.status_code == 201, create_owner_g.text

        create_other_g = client.post(
            "/api/v1/godowns",
            json={"godown_id": "GDN_RUN_OTHER", "name": "Other Godown"},
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert create_other_g.status_code == 201, create_other_g.text

        owner_run = create_test_run(
            godown_id="GDN_RUN_OWNER",
            camera_id="CAM_OWNER",
            zone_id=None,
            run_name="Owner Run",
            write_video=lambda f: f.write(b"owner-test-video"),
        )
        other_run = create_test_run(
            godown_id="GDN_RUN_OTHER",
            camera_id="CAM_OTHER",
            zone_id=None,
            run_name="Other Run",
            write_video=lambda f: f.write(b"other-test-video"),
        )

        owner_list = client.get("/api/v1/test-runs", headers={"Authorization": f"Bearer {owner_token}"})
        assert owner_list.status_code == 200, owner_list.text
        owner_ids = {r["run_id"] for r in owner_list.json().get("items", [])}
        assert owner_run["run_id"] in owner_ids
        assert other_run["run_id"] not in owner_ids

        forbidden_detail = client.get(
            f"/api/v1/test-runs/{other_run['run_id']}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert forbidden_detail.status_code == 403
