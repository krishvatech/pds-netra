"""
Preflight checks for PDS Netra edge node.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path
from typing import List, Optional

from .config import load_settings


def _check_mqtt(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str).expanduser()
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def _check_override(path_str: str) -> List[str]:
    errors: List[str] = []
    path = _resolve_path(path_str)
    if not path.exists():
        errors.append(f"Override file not found: {path}")
        return errors
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("mode") == "test":
            overrides = data.get("camera_overrides") or {}
            for cam_id, cfg in overrides.items():
                if cfg.get("source_type") == "file":
                    file_path = cfg.get("path")
                    if not file_path:
                        errors.append(f"Override missing path for camera {cam_id}")
                        continue
                    resolved = _resolve_path(str(file_path))
                    if not resolved.exists():
                        errors.append(f"Override file missing for camera {cam_id}: {resolved}")
    except Exception as exc:
        errors.append(f"Failed to parse override file: {exc}")
    return errors


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="PDS Netra edge preflight checks")
    parser.add_argument("--config", default="config/pds_netra_config.yaml")
    args = parser.parse_args(argv or sys.argv[1:])

    settings = load_settings(args.config)
    errors: List[str] = []

    # MQTT check
    mqtt_ok = _check_mqtt(settings.mqtt_broker_host, settings.mqtt_broker_port)
    if not mqtt_ok:
        errors.append(
            f"MQTT broker not reachable at {settings.mqtt_broker_host}:{settings.mqtt_broker_port}"
        )

    # Test video paths
    for cam in settings.cameras:
        if cam.test_video:
            resolved = _resolve_path(cam.test_video)
            if not resolved.exists():
                errors.append(f"Test video missing for camera {cam.id}: {resolved}")

    # Override path
    override_path = os.getenv("EDGE_OVERRIDE_PATH")
    if override_path:
        errors.extend(_check_override(override_path))

    if errors:
        print("Preflight checks failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Preflight checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
