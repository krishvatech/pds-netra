"""
Play the configured siren once for testing.

Usage:
  python3 tools/play_siren.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Allow running this script from any working directory.
EDGE_ROOT = Path(__file__).resolve().parents[1]
if str(EDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(EDGE_ROOT))
load_dotenv(EDGE_ROOT / ".env", override=True)

from app.actuators.speaker import SpeakerService


def main() -> int:
    speaker = SpeakerService()
    speaker.trigger(reason="FIRE_DETECTED", camera_id="TEST_CAMERA", event_id="TEST_EVENT")
    duration = max(1.0, speaker.config.duration_sec)
    # Keep process alive long enough for the timer to stop playback.
    time.sleep(duration + 1.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())