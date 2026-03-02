import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:////tmp/pds_netra_test_camera_zones.db")
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


def _client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_camera_zone_pixels_per_meter_roundtrip() -> None:
    gid = f"GDN_ZONES_{uuid.uuid4().hex[:8]}"
    cid = f"CAM_ZONES_{uuid.uuid4().hex[:8]}"

    with _client() as client:
        godown_resp = client.post("/api/v1/godowns", json={"godown_id": gid, "name": gid})
        assert godown_resp.status_code == 200, godown_resp.text

        cam_resp = client.post(
            "/api/v1/cameras",
            json={
                "camera_id": cid,
                "godown_id": gid,
                "rtsp_url": "rtsp://example/cam",
                "is_active": True,
            },
        )
        assert cam_resp.status_code == 200, cam_resp.text

        put_resp = client.put(
            f"/api/v1/cameras/{cid}/zones",
            params={"godown_id": gid},
            json={
                "zones": [
                    {
                        "id": "zone_a",
                        "polygon": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
                        "pixels_per_meter": 130.0,
                    }
                ]
            },
        )
        assert put_resp.status_code == 200, put_resp.text

        get_resp = client.get(f"/api/v1/cameras/{cid}/zones", params={"godown_id": gid})
        assert get_resp.status_code == 200, get_resp.text
        zones = get_resp.json().get("zones") or []
        assert len(zones) == 1
        assert zones[0]["id"] == "zone_a"
        assert float(zones[0]["pixels_per_meter"]) == 130.0


def test_camera_zone_pixels_per_meter_validation() -> None:
    gid = f"GDN_ZONES_{uuid.uuid4().hex[:8]}"
    cid = f"CAM_ZONES_{uuid.uuid4().hex[:8]}"

    with _client() as client:
        godown_resp = client.post("/api/v1/godowns", json={"godown_id": gid, "name": gid})
        assert godown_resp.status_code == 200, godown_resp.text

        cam_resp = client.post(
            "/api/v1/cameras",
            json={
                "camera_id": cid,
                "godown_id": gid,
                "rtsp_url": "rtsp://example/cam",
                "is_active": True,
            },
        )
        assert cam_resp.status_code == 200, cam_resp.text

        bad_resp = client.put(
            f"/api/v1/cameras/{cid}/zones",
            params={"godown_id": gid},
            json={
                "zones": [
                    {
                        "id": "zone_bad",
                        "polygon": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
                        "pixels_per_meter": 0,
                    }
                ]
            },
        )
        assert bad_resp.status_code == 422
