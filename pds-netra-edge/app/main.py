"""
Entry point for the PDS Netra edge node.

Usage (from project root)::

    python -m app.main --config config/pds_netra_config.yaml --device cpu

This script loads the configuration, initializes logging, connects to
the MQTT broker, starts video processing pipelines for each camera, and
launches periodic health heartbeats. It runs until interrupted.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import List

from .config import load_settings, Settings
from .logging_config import setup_logging
from .events.mqtt_client import MQTTClient
from .runtime.camera_loop import start_camera_loops
from .runtime.scheduler import Scheduler


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PDS Netra Edge Node")
    parser.add_argument(
        "--config",
        type=str,
        default="config/pds_netra_config.yaml",
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        choices=["cpu", "cuda"],
        help="Device for running inference (cpu or cuda)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    setup_logging(level=log_level)
    logger = logging.getLogger("main")
    try:
        settings: Settings = load_settings(args.config)
    except Exception as exc:
        logger.error("Failed to load configuration: %s", exc)
        return 1
    logger.info("Loaded settings for godown %s", settings.godown_id)
    # Initialize MQTT client
    mqtt_client = MQTTClient(settings)
    mqtt_client.connect()
    # Start camera processing loops and obtain camera health state mapping
    threads, camera_states = start_camera_loops(settings, mqtt_client, device=args.device)
    # Start periodic scheduler, passing camera state for health monitoring
    scheduler = Scheduler(settings, mqtt_client, camera_states=camera_states)
    scheduler.start()
    logger.info("Edge node started; press Ctrl+C to stop")
    try:
        while True:
            # Keep the main thread alive
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down edge node…")
    finally:
        scheduler.stop()
        mqtt_client.stop()
        # Threads are daemon threads; they will exit automatically when main exits
    return 0


if __name__ == "__main__":
    sys.exit(main())