"""
Camera tamper and health heuristics for PDS Netra.

This module provides lightweight tamper detection on frames and returns
structured candidates for the caller to publish. It maintains state for
consecutive-frame gating and baseline updates to avoid false positives.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict
import datetime

import cv2  # type: ignore
import numpy as np  # type: ignore

from ..config import HealthConfig


@dataclass
class TamperEventCandidate:
    """Container describing a potential tamper event."""

    event_type: str
    reason: str
    confidence: float
    metrics: Dict[str, float]
    snapshot: Optional[np.ndarray] = None


@dataclass
class CameraTamperState:
    """Maintain state across frames for tamper detection heuristics."""

    baseline: Optional[np.ndarray] = None
    baseline_mean: Optional[float] = None
    low_light_counter: int = 0
    low_light_clear: int = 0
    blackout_counter: int = 0
    blackout_clear: int = 0
    uniform_counter: int = 0
    uniform_clear: int = 0
    blur_counter: int = 0
    blur_clear: int = 0
    moved_counter: int = 0
    moved_clear: int = 0


def _clamp(value: float) -> float:
    return float(min(max(value, 0.0), 1.0))


def analyze_frame_for_tamper(
    camera_id: str,
    frame: np.ndarray,
    now_utc: datetime.datetime,
    config: HealthConfig,
    state: CameraTamperState,
) -> List[TamperEventCandidate]:
    """
    Analyze a single frame for tampering conditions.

    Returns a list of candidates. The caller handles cooldowns and publishing.
    """
    candidates: List[TamperEventCandidate] = []

    if not config.enabled:
        grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(grey, (64, 64), interpolation=cv2.INTER_AREA)
        state.baseline = small
        state.baseline_mean = float(np.mean(grey))
        return candidates

    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_brightness = float(np.mean(grey))
    stddev_brightness = float(np.std(grey))
    lap = cv2.Laplacian(grey, cv2.CV_64F)
    lap_var = float(lap.var())

    small = cv2.resize(grey, (64, 64), interpolation=cv2.INTER_AREA)
    diff_ratio = None
    if state.baseline is not None:
        diff = cv2.absdiff(state.baseline, small)
        diff_ratio = float(np.mean(diff)) / 255.0

    if state.baseline_mean is None:
        state.baseline_mean = mean_brightness

    # === Condition checks ===
    black_frame_now = mean_brightness < config.black_frame_threshold
    sudden_blackout_now = False
    if state.baseline_mean and state.baseline_mean > config.blackout_min_baseline:
        sudden_blackout_now = mean_brightness < state.baseline_mean * (1 - config.blackout_drop_ratio)

    low_light_now = mean_brightness < config.low_light_threshold and not black_frame_now
    uniform_now = stddev_brightness < config.uniform_std_threshold and not black_frame_now
    blur_now = lap_var < config.blur_threshold and not black_frame_now
    moved_now = diff_ratio is not None and diff_ratio > config.moved_diff_threshold

    # === LOW LIGHT ===
    if low_light_now:
        state.low_light_counter += 1
        state.low_light_clear = 0
        if state.low_light_counter >= config.low_light_consecutive_frames:
            confidence = _clamp(1.0 - (mean_brightness / max(config.low_light_threshold, 1e-6)))
            snapshot = frame.copy() if config.snapshot_on_tamper else None
            candidates.append(
                TamperEventCandidate(
                    event_type="LOW_LIGHT",
                    reason="LOW_LIGHT",
                    confidence=confidence,
                    metrics={"mean": mean_brightness, "std": stddev_brightness},
                    snapshot=snapshot,
                )
            )
            state.low_light_counter = 0
    else:
        state.low_light_clear += 1
        if state.low_light_clear >= config.clear_consecutive_frames:
            state.low_light_counter = 0

    # === BLACKOUT ===
    if black_frame_now or sudden_blackout_now:
        state.blackout_counter += 1
        state.blackout_clear = 0
        if state.blackout_counter >= max(3, config.low_light_consecutive_frames // 2):
            reason = "BLACK_FRAME" if black_frame_now else "SUDDEN_BLACKOUT"
            confidence = _clamp(1.0 - (mean_brightness / max(state.baseline_mean or 1.0, 1e-6)))
            snapshot = frame.copy() if config.snapshot_on_tamper else None
            candidates.append(
                TamperEventCandidate(
                    event_type="CAMERA_TAMPERED",
                    reason=reason,
                    confidence=confidence,
                    metrics={"mean": mean_brightness, "baseline_mean": float(state.baseline_mean or 0.0)},
                    snapshot=snapshot,
                )
            )
            state.blackout_counter = 0
    else:
        state.blackout_clear += 1
        if state.blackout_clear >= config.clear_consecutive_frames:
            state.blackout_counter = 0

    # === UNIFORM / LENS BLOCKED ===
    if uniform_now and mean_brightness >= config.low_light_threshold:
        state.uniform_counter += 1
        state.uniform_clear = 0
        if state.uniform_counter >= config.blocked_consecutive_frames:
            reason = "UNIFORM_FRAME" if stddev_brightness < (config.uniform_std_threshold * 0.5) else "LENS_BLOCKED"
            confidence = _clamp(1.0 - (stddev_brightness / max(config.uniform_std_threshold, 1e-6)))
            snapshot = frame.copy() if config.snapshot_on_tamper else None
            candidates.append(
                TamperEventCandidate(
                    event_type="CAMERA_TAMPERED",
                    reason=reason,
                    confidence=confidence,
                    metrics={"mean": mean_brightness, "std": stddev_brightness},
                    snapshot=snapshot,
                )
            )
            state.uniform_counter = 0
    else:
        state.uniform_clear += 1
        if state.uniform_clear >= config.clear_consecutive_frames:
            state.uniform_counter = 0

    # === BLUR ===
    if blur_now and mean_brightness >= config.low_light_threshold:
        state.blur_counter += 1
        state.blur_clear = 0
        if state.blur_counter >= config.blur_consecutive_frames:
            confidence = _clamp(1.0 - (lap_var / max(config.blur_threshold, 1e-6)))
            snapshot = frame.copy() if config.snapshot_on_tamper else None
            candidates.append(
                TamperEventCandidate(
                    event_type="CAMERA_TAMPERED",
                    reason="BLURRY_FRAME",
                    confidence=confidence,
                    metrics={"lap_var": lap_var},
                    snapshot=snapshot,
                )
            )
            state.blur_counter = 0
    else:
        state.blur_clear += 1
        if state.blur_clear >= config.clear_consecutive_frames:
            state.blur_counter = 0

    # === CAMERA MOVED ===
    if moved_now:
        state.moved_counter += 1
        state.moved_clear = 0
        if state.moved_counter >= config.moved_consecutive_frames:
            confidence = _clamp(float(diff_ratio or 0.0))
            snapshot = frame.copy() if config.snapshot_on_tamper else None
            candidates.append(
                TamperEventCandidate(
                    event_type="CAMERA_TAMPERED",
                    reason="CAMERA_MOVED",
                    confidence=confidence,
                    metrics={"diff": float(diff_ratio or 0.0)},
                    snapshot=snapshot,
                )
            )
            state.moved_counter = 0
    else:
        state.moved_clear += 1
        if state.moved_clear >= config.clear_consecutive_frames:
            state.moved_counter = 0

    # === Baseline update ===
    tamper_active = any([low_light_now, black_frame_now, sudden_blackout_now, uniform_now, blur_now, moved_now])
    if not tamper_active:
        if state.baseline is None:
            state.baseline = small
        else:
            alpha = 0.01
            baseline_f = state.baseline.astype(np.float32)
            new_f = small.astype(np.float32)
            baseline_updated = baseline_f * (1 - alpha) + new_f * alpha
            state.baseline = baseline_updated.astype(state.baseline.dtype)
        # Update baseline mean slowly
        if state.baseline_mean is None:
            state.baseline_mean = mean_brightness
        else:
            state.baseline_mean = state.baseline_mean * 0.99 + mean_brightness * 0.01

    return candidates
