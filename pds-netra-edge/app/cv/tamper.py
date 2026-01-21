"""
Camera tamper and health heuristics for PDS Netra.

This module provides simple, computationally efficient functions to
detect camera tampering conditions such as black frames, lens blocked,
blurred images, and camera movement. These heuristics operate on
individual frames and maintain minimal state across frames to
aggregate evidence over time. Thresholds and durations for
detection are configurable via the YAML ``health`` section in
``pds_netra_config.yaml``.

The output of tamper analysis is a list of ``TamperEventCandidate``
instances, which the caller can use to construct and publish
MQTT events. Deduplication and cooldown handling should be
implemented by the caller based on these candidates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
import datetime

import cv2  # type: ignore
import numpy as np  # type: ignore

from ..config import HealthConfig


@dataclass
class TamperEventCandidate:
    """Simple container describing a potential tamper event.

    Attributes
    ----------
    reason: str
        The inferred reason for the tamper (e.g. "BLACK_FRAME", "LENS_BLOCKED").
    confidence: float
        Confidence score between 0 and 1 representing how strongly the heuristic
        supports this tamper reason.
    snapshot: Optional[np.ndarray]
        Optional BGR image of the frame in which the tamper was detected. Only
        provided if snapshot_on_tamper is enabled.
    """

    reason: str
    confidence: float
    snapshot: Optional[np.ndarray] = None


@dataclass
class CameraTamperState:
    """Maintain state across frames for tamper detection heuristics."""

    # Baseline grayscale image for detecting camera movement. Stored as a small
    # resized image to reduce computational overhead. ``None`` until first frame.
    baseline: Optional[np.ndarray] = None
    # Counters for consecutive frames satisfying various tamper conditions.
    low_light_counter: int = 0
    blocked_counter: int = 0
    blur_counter: int = 0
    moved_counter: int = 0
    # Last tamper event reason emitted for deduplication.
    last_tamper_reason: Optional[str] = None
    # UTC time of last tamper event emitted.
    last_tamper_time: Optional[datetime.datetime] = None


def analyze_frame_for_tamper(
    camera_id: str,
    frame: np.ndarray,
    now_utc: datetime.datetime,
    config: HealthConfig,
    state: CameraTamperState,
) -> List[TamperEventCandidate]:
    """
    Analyze a single frame for tampering conditions.

    This function computes a handful of lightweight metrics on the
    provided frame to determine whether the camera may have been
    tampered with. Detected conditions include black frames, low light,
    lens obstruction, blur, and camera movement. It maintains counters
    in the provided ``state`` to require that conditions persist for
    multiple frames before emitting an event. When a tamper is
    identified, a ``TamperEventCandidate`` is appended to the returned
    list.

    Parameters
    ----------
    camera_id: str
        Identifier for the camera producing the frame.
    frame: np.ndarray
        The current BGR frame from the video stream.
    now_utc: datetime.datetime
        The UTC timestamp corresponding to when the frame was captured.
    config: HealthConfig
        Per-camera configuration specifying thresholds and durations for
        tamper detection.
    state: CameraTamperState
        Mutable state object used to accumulate evidence across frames.

    Returns
    -------
    List[TamperEventCandidate]
        A list of detected tamper conditions. The caller is responsible for
        deduplicating and publishing events.
    """
    candidates: List[TamperEventCandidate] = []

    # If monitoring is disabled, update baseline and return
    if not config.enabled:
        grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(grey, (64, 64), interpolation=cv2.INTER_AREA)
        state.baseline = small
        return candidates

    # Convert to grayscale for analysis
    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Compute basic statistics
    mean_brightness = float(np.mean(grey))
    stddev_brightness = float(np.std(grey))
    # Laplacian variance for blur detection
    lap = cv2.Laplacian(grey, cv2.CV_64F)
    lap_var = float(lap.var())

    # Resize frame to small footprint for movement analysis
    small = cv2.resize(grey, (64, 64), interpolation=cv2.INTER_AREA)
    diff_ratio: Optional[float] = None
    if state.baseline is not None:
        # Compute mean absolute difference normalized to [0,1]
        diff = cv2.absdiff(state.baseline, small)
        diff_ratio = float(np.mean(diff)) / 255.0

    # === Low light and black frame detection ===
    if mean_brightness < config.low_light_threshold:
        state.low_light_counter += 1
        # Determine reason: extremely low brightness implies black frame
        if mean_brightness < config.low_light_threshold * 0.2:
            reason = "BLACK_FRAME"
        else:
            reason = "LOW_LIGHT"
        if state.low_light_counter >= config.low_light_consecutive_frames:
            # Confidence increases as brightness decreases
            confidence = 1.0 - (mean_brightness / max(config.low_light_threshold, 1e-6))
            snapshot = frame.copy() if config.snapshot_on_tamper else None
            candidates.append(TamperEventCandidate(reason=reason, confidence=float(min(max(confidence, 0.0), 1.0)), snapshot=snapshot))
            # Reset counter to avoid continuous spamming; will build up again if condition persists
            state.low_light_counter = 0
    else:
        state.low_light_counter = 0

    # === Lens blocked (uniform frame) detection ===
    if stddev_brightness < config.blocked_stddev_threshold and mean_brightness >= config.low_light_threshold:
        state.blocked_counter += 1
        if state.blocked_counter >= config.blocked_consecutive_frames:
            # Confidence inversely proportional to stddev; smaller stddev means more uniform
            confidence = 1.0 - (stddev_brightness / max(config.blocked_stddev_threshold, 1e-6))
            snapshot = frame.copy() if config.snapshot_on_tamper else None
            candidates.append(TamperEventCandidate(reason="LENS_BLOCKED", confidence=float(min(max(confidence, 0.0), 1.0)), snapshot=snapshot))
            state.blocked_counter = 0
    else:
        state.blocked_counter = 0

    # === Blur detection ===
    if lap_var < config.blur_threshold:
        state.blur_counter += 1
        if state.blur_counter >= config.blur_consecutive_frames:
            # Confidence inversely proportional to variance; smaller variance means blurrier
            confidence = 1.0 - (lap_var / max(config.blur_threshold, 1e-6))
            snapshot = frame.copy() if config.snapshot_on_tamper else None
            candidates.append(TamperEventCandidate(reason="BLUR", confidence=float(min(max(confidence, 0.0), 1.0)), snapshot=snapshot))
            state.blur_counter = 0
    else:
        state.blur_counter = 0

    # === Camera moved detection ===
    if diff_ratio is not None and diff_ratio > config.tamper_frame_diff_threshold:
        state.moved_counter += 1
        if state.moved_counter >= config.moved_consecutive_frames:
            confidence = float(min(max(diff_ratio, 0.0), 1.0))
            snapshot = frame.copy() if config.snapshot_on_tamper else None
            candidates.append(TamperEventCandidate(reason="CAMERA_MOVED", confidence=confidence, snapshot=snapshot))
            # Update baseline to current to avoid repeated triggers on same move
            state.baseline = small
            state.moved_counter = 0
    else:
        state.moved_counter = 0
        # If not moved, gradually update baseline with an exponential moving average to adapt to slow changes
        if state.baseline is None:
            state.baseline = small
        else:
            alpha = 0.01
            # Use weighted average to slowly adapt baseline; convert to float for precision then back to uint8
            baseline_f = state.baseline.astype(np.float32)
            new_f = small.astype(np.float32)
            baseline_updated = baseline_f * (1 - alpha) + new_f * alpha
            state.baseline = baseline_updated.astype(state.baseline.dtype)

    return candidates
