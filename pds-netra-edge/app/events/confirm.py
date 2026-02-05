"""
Confirmation gate shared by edge events before they are sent to MQTT.
"""

from __future__ import annotations

import time
from collections import deque, defaultdict
from dataclasses import dataclass
from typing import Deque, Dict, Tuple, Optional


@dataclass
class ConfirmConfig:
    count_required: int = 3
    window_seconds: float = 8.0
    persist_seconds: float = 10.0
    confirm_cooldown_seconds: float = 3.0


class ConfirmGate:
    """
    Maintain rolling buffers per (camera_id, rule_id) to confirm detections.
    """

    def __init__(self, cfg: ConfirmConfig | None = None) -> None:
        self.cfg = cfg or ConfirmConfig()
        self._buf: Dict[Tuple[str, str], Deque[Tuple[float, Optional[int]]]] = defaultdict(
            lambda: deque(maxlen=50)
        )
        self._track_first_seen: Dict[Tuple[str, str, int], float] = {}
        self._last_confirm: Dict[Tuple[str, str], float] = {}

    def push(
        self,
        *,
        camera_id: str,
        rule_id: str,
        now: float,
        track_id: Optional[int],
    ) -> bool:
        key = (camera_id, rule_id)
        last = self._last_confirm.get(key)
        if last is not None and (now - last) < self.cfg.confirm_cooldown_seconds:
            return False

        queue = self._buf[key]
        queue.append((now, track_id))
        cutoff = now - self.cfg.window_seconds
        while queue and queue[0][0] < cutoff:
            queue.popleft()

        if len(queue) >= self.cfg.count_required:
            self._last_confirm[key] = now
            return True

        if track_id is not None:
            track_key = (camera_id, rule_id, int(track_id))
            first = self._track_first_seen.get(track_key)
            if first is None:
                self._track_first_seen[track_key] = now
            elif (now - first) >= self.cfg.persist_seconds:
                self._last_confirm[key] = now
                return True

        return False

    def reset_if_no_detections(
        self,
        *,
        camera_id: str,
        rule_id: str,
        now: float,
        idle_seconds: float = 30.0,
    ) -> None:
        key = (camera_id, rule_id)
        queue = self._buf.get(key)
        if not queue:
            return
        if (now - queue[-1][0]) >= idle_seconds:
            self._buf.pop(key, None)
            to_remove = [
                tkey
                for tkey in self._track_first_seen.keys()
                if tkey[0] == camera_id and tkey[1] == rule_id
            ]
            for tkey in to_remove:
                self._track_first_seen.pop(tkey, None)
