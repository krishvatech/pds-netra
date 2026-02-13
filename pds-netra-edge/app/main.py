"""
Entry point for the PDS Netra edge node.

Usage (from project root)::

    python -m app.main --config config/pds_netra_config.yaml --device cuda:0

This script loads the configuration, initializes logging, connects to
the MQTT broker, starts video processing pipelines for each camera, and
launches periodic health heartbeats. It runs until interrupted.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from typing import List

from dotenv import load_dotenv

from .config import load_settings, Settings
from .logging_config import setup_logging
from .events.mqtt_client import MQTTClient
from .actuators.speaker import SpeakerService
from .runtime.camera_loop import start_camera_loops
from .runtime.scheduler import Scheduler
from .runtime.watchdog import EdgeWatchdog
from .preflight import main as preflight_main
from .rules.remote import fetch_rule_configs
from .cameras.remote import fetch_camera_configs


ALLOWED_DEVICES = {"auto", "cpu", "cuda:0", "tensorrt"}
DEVICE_ALIASES = {"cuda": "cuda:0"}


def _normalize_device(raw: str | None) -> str | None:
    if raw is None:
        return None
    val = str(raw).strip().lower()
    if not val:
        return None
    return DEVICE_ALIASES.get(val, val)


def _torch_cuda_snapshot() -> tuple[str | None, bool, str | None]:
    try:
        import torch
    except Exception:
        return None, False, None
    version = getattr(torch, "__version__", None)
    try:
        cuda_available = bool(torch.cuda.is_available())
    except Exception:
        cuda_available = False
    gpu_name = None
    if cuda_available:
        try:
            gpu_name = str(torch.cuda.get_device_name(0))
        except Exception:
            gpu_name = None
    return version, cuda_available, gpu_name


def _resolve_inference_device(cli_device: str | None, logger: logging.Logger) -> str:
    requested_raw = cli_device if cli_device is not None else os.getenv("EDGE_DEVICE", "auto")
    requested = _normalize_device(requested_raw)
    if requested and requested not in ALLOWED_DEVICES:
        logger.warning(
            "Unsupported EDGE_DEVICE/--device value '%s'. Falling back to auto-select.",
            requested_raw,
        )
        requested = "auto"

    torch_version, cuda_available, gpu_name = _torch_cuda_snapshot()
    logger.info("torch version: %s", torch_version or "not installed")
    logger.info("torch.cuda.is_available(): %s", cuda_available)
    logger.info("torch.cuda.get_device_name(0): %s", gpu_name or "N/A")

    if requested in {None, "auto"}:
        if cuda_available:
            logger.info("Auto-selecting cuda:0 (CUDA is available).")
            return "cuda:0"
        logger.warning(
            "========== GPU WARNING ==========\n"
            "CUDA is not available. Falling back to CPU inference.\n"
            "Set up CUDA-enabled PyTorch/TensorRT on Jetson for GPU inference.\n"
            "================================="
        )
        return "cpu"

    if requested in {"cuda:0", "tensorrt"} and not cuda_available:
        logger.warning(
            "========== GPU WARNING ==========\n"
            "Requested device '%s' but CUDA is not available.\n"
            "Falling back to CPU inference.\n"
            "=================================",
            requested,
        )
        return "cpu"
    return requested


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PDS Netra Edge Node")
    parser.add_argument(
        "--config",
        type=str,
        default=os.getenv("EDGE_CONFIG_PATH", "config/pds_netra_config.yaml"),
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=os.getenv("EDGE_DEVICE", "auto"),
        choices=["auto", "cpu", "cuda", "cuda:0", "tensorrt"],
        help="Inference device (auto | cpu | cuda:0 | tensorrt). "
        "Alias: cuda -> cuda:0. Default: auto.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Run preflight checks and exit",
    )
    parser.add_argument(
        "--preflight-on-start",
        action="store_true",
        help="Run preflight checks before starting the edge node",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    # Load local .env so runtime flags (alerts, overrides, models) are honored.
    load_dotenv()
    args = parse_args(argv or sys.argv[1:])
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    setup_logging(level=log_level)
    logger = logging.getLogger("main")
    logger.info(
        "Alert config: EDGE_ALERT_ON_PERSON=%s EDGE_ALERT_ON_CLASSES=%s EDGE_ALERT_SEVERITY=%s EDGE_ALERT_PERSON_COOLDOWN=%s",
        os.getenv("EDGE_ALERT_ON_PERSON", "false"),
        os.getenv("EDGE_ALERT_ON_CLASSES", ""),
        os.getenv("EDGE_ALERT_SEVERITY", "warning"),
        os.getenv("EDGE_ALERT_PERSON_COOLDOWN", "10"),
    )
    if args.preflight:
        return preflight_main(["--config", args.config])
    if args.preflight_on_start:
        preflight_rc = preflight_main(["--config", args.config])
        if preflight_rc != 0:
            return preflight_rc
    try:
        settings: Settings = load_settings(args.config)
    except Exception as exc:
        logger.error("Failed to load configuration: %s", exc)
        return 1
    logger.info("Loaded settings for godown %s", settings.godown_id)
    effective_device = _resolve_inference_device(args.device, logger)
    logger.info("Inference device: %s", effective_device)
    logger.info(
        "Selected inference backend=%s device=%s",
        "tensorrt" if effective_device == "tensorrt" else "pytorch",
        effective_device,
    )
    rules_source = os.getenv("EDGE_RULES_SOURCE", "backend").lower()
    if rules_source == "backend":
        backend_url = os.getenv("EDGE_BACKEND_URL", os.getenv("BACKEND_URL", "http://127.0.0.1:8001"))
        fetched = fetch_rule_configs(backend_url, settings.godown_id)
        if fetched is not None:
            settings.rules = fetched
            logger.info("Loaded %s rules from backend", len(fetched))
    cameras_source = os.getenv("EDGE_CAMERAS_SOURCE", "backend").lower()
    if cameras_source == "backend":
        backend_url = os.getenv("EDGE_BACKEND_URL", os.getenv("BACKEND_URL", "http://127.0.0.1:8001"))
        cams = fetch_camera_configs(backend_url, settings.godown_id)

        # SAFETY: if backend fails, keep YAML cameras so current system never breaks
        if cams is not None:
            settings.cameras = cams
            logger.info("Loaded %s cameras from backend", len(cams))

    # Initialize MQTT client and speaker service
    speaker = SpeakerService()
    mqtt_client = MQTTClient(settings, speaker_service=speaker)
    mqtt_client.connect()
    mqtt_client.start_outbox()
    # Start camera processing loops and obtain camera health state mapping
    threads, camera_states, restart_camera = start_camera_loops(settings, mqtt_client, device=effective_device)
    mqtt_client.set_camera_states(camera_states)
    # Start periodic scheduler, passing camera state for health monitoring
    scheduler = Scheduler(settings, mqtt_client, camera_states=camera_states)
    scheduler.start()
    watchdog = EdgeWatchdog(
        settings=settings,
        camera_states=camera_states,
        restart_camera=restart_camera,
        mqtt_client=mqtt_client,
        outbox=mqtt_client.outbox,
    )
    watchdog.start()
    logger.info("Edge node started; press Ctrl+C to stop")
    try:
        while True:
            # Keep the main thread alive
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down edge node…")
    finally:
        watchdog.stop()
        scheduler.stop()
        mqtt_client.stop()
        # Threads are daemon threads; they will exit automatically when main exits
    return 0


if __name__ == "__main__":
    sys.exit(main())
