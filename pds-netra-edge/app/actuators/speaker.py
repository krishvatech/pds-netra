"""
Speaker/siren actuator for Jetson edge devices.

Plays a WAV file via `aplay` in a non-blocking way with cooldown protection.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Tuple


DEFAULT_EVENT_TYPES = {
    "AFTER_HOURS_PERSON_DETECTED",
    "PERSON_INTRUSION",
    "FIRE_DETECTED",
    "WATCHLIST_MATCH",
}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


@dataclass
class SpeakerConfig:
    device: str = "default"
    siren_file: str = "/opt/app/config/siren_16bit.wav"
    cooldown_sec: float = 60.0
    duration_sec: float = 10.0
    enabled: bool = True
    event_types: Set[str] = field(default_factory=lambda: set(DEFAULT_EVENT_TYPES))

    @classmethod
    def from_env(cls) -> "SpeakerConfig":
        raw_types = os.getenv("EDGE_SIREN_EVENT_TYPES", "")
        if raw_types.strip():
            event_types = {t.strip().upper() for t in raw_types.split(",") if t.strip()}
        else:
            event_types = set(DEFAULT_EVENT_TYPES)
        return cls(
            device=os.getenv("EDGE_SPEAKER_DEVICE", "default"),
            siren_file=os.getenv("EDGE_SIREN_FILE", "/opt/app/config/siren_16bit.wav"),
            cooldown_sec=_env_float("EDGE_SIREN_COOLDOWN_SEC", 60.0),
            duration_sec=_env_float("EDGE_SIREN_DURATION_SEC", 10.0),
            enabled=_env_bool("EDGE_SIREN_ENABLED", True),
            event_types=event_types,
        )


class SpeakerService:
    def __init__(self, config: Optional[SpeakerConfig] = None, logger: Optional[logging.Logger] = None) -> None:
        self.config = config or SpeakerConfig.from_env()
        self.logger = logger or logging.getLogger("speaker")
        self._lock = threading.Lock()
        self._last_play_ts: Dict[Tuple[str, str], float] = {}
        self._available_checked = False
        self._available = False

    def _check_available(self) -> bool:
        if self._available_checked:
            return self._available
        self._available_checked = True
        if not self.config.enabled:
            self._available = False
            return False
        if not shutil.which("aplay"):
            self.logger.warning("Speaker disabled: aplay not found on PATH")
            self._available = False
            return False
        if not os.path.isfile(self.config.siren_file):
            self.logger.warning("Speaker disabled: siren file missing path=%s", self.config.siren_file)
            self._available = False
            return False
        self._available = True
        return True

    def _confidence_ok(self, confidence: Optional[float]) -> bool:
        if confidence is None:
            return True
        try:
            return float(confidence) >= 0.0
        except Exception:
            return False

    def trigger(self, *, reason: str, camera_id: str, event_id: str, confidence: Optional[float] = None) -> None:
        if not reason:
            return
        reason_norm = reason.strip().upper()
        if not reason_norm or reason_norm not in self.config.event_types:
            return
        if not self._confidence_ok(confidence):
            return
        if not self._check_available():
            return
        now = time.monotonic()
        key = (camera_id or "unknown", reason_norm)
        with self._lock:
            last = self._last_play_ts.get(key)
            if last is not None and now - last < max(0.0, self.config.cooldown_sec):
                return
            self._last_play_ts[key] = now
        try:
            proc = subprocess.Popen(
                ["aplay", "-D", self.config.device, "-q", self.config.siren_file],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            self.logger.warning("Speaker disabled: aplay not found on PATH")
            self._available = False
            return
        except Exception as exc:
            self.logger.warning("Speaker trigger failed camera=%s event=%s reason=%s error=%s", camera_id, event_id, reason_norm, exc)
            return
        self.logger.info("Speaker triggered camera=%s event=%s reason=%s", camera_id, event_id, reason_norm)
        duration = max(0.1, self.config.duration_sec)
        timer = threading.Timer(duration, self._stop_process, args=(proc, camera_id, event_id, reason_norm))
        timer.daemon = True
        timer.start()

    def _stop_process(self, proc: subprocess.Popen, camera_id: str, event_id: str, reason: str) -> None:
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=1.0)
                except Exception:
                    proc.kill()
        except Exception as exc:
            self.logger.debug(
                "Speaker stop failed camera=%s event=%s reason=%s error=%s",
                camera_id,
                event_id,
                reason,
                exc,
            )
