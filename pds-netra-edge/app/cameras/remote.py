"""
Fetch camera configurations from the backend API.

Uses:
GET /api/v1/godowns/{godown_id}

Your backend response example:
{
  "cameras": [
    {
      "camera_id": "demo",
      "rtsp_url": "rtsp://...",
      "is_active": true,
      "zones_json": null
    }
  ]
}
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import List, Optional

from ..config import CameraConfig, ZoneConfig


def _parse_zones(zones_json) -> List[ZoneConfig]:
    """Support zones_json as dict/list/JSON-string. Return [] if missing."""
    if not zones_json:
        return []

    # if zones_json is a JSON string, parse it
    if isinstance(zones_json, str):
        try:
            zones_json = json.loads(zones_json)
        except Exception:
            return []

    zones = None
    if isinstance(zones_json, dict):
        zones = zones_json.get("zones")
    elif isinstance(zones_json, list):
        zones = zones_json

    if not isinstance(zones, list):
        return []

    out: List[ZoneConfig] = []
    for z in zones:
        if not isinstance(z, dict):
            continue
        zid = z.get("id")
        poly = z.get("polygon")
        if not zid or not isinstance(poly, list):
            continue
        try:
            out.append(ZoneConfig(id=str(zid), polygon=poly))
        except Exception:
            continue
    return out


def fetch_camera_configs(
    backend_url: str,
    godown_id: str,
    timeout_sec: float = 3.0,
) -> Optional[List[CameraConfig]]:
    logger = logging.getLogger("cameras.remote")
    base = backend_url.rstrip("/")
    url = f"{base}/api/v1/godowns/{godown_id}"

    try:
        with urllib.request.urlopen(url, timeout=timeout_sec) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.warning("Failed to fetch cameras from %s: %s", url, exc)
        return None

    if not isinstance(payload, dict):
        return None

    cams = payload.get("cameras")
    if not isinstance(cams, list):
        return None

    out: List[CameraConfig] = []
    for c in cams:
        if not isinstance(c, dict):
            continue

        # ignore inactive cameras
        if c.get("is_active") is False:
            continue

        cam_id = c.get("camera_id") or c.get("id")
        rtsp = c.get("rtsp_url")
        if not cam_id or not rtsp:
            continue

        zones = _parse_zones(c.get("zones_json"))

        # IMPORTANT: do NOT change your health logic.
        # Keep health=None, so your existing code uses HealthConfig() defaults.
        out.append(
            CameraConfig(
                id=str(cam_id),
                rtsp_url=str(rtsp),
                test_video=None,
                zones=zones,
                health=None,
            )
        )

    return out