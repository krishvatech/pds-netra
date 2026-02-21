from __future__ import annotations

import os
import time
from pathlib import Path

from app.services.live_frames import enforce_single_live_frame, remove_live_frame_artifacts


def _write_file(path: Path, content: bytes = b"x", *, mtime: float | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def test_enforce_single_live_frame_prunes_legacy_when_latest_exists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PDS_LIVE_ENFORCE_SINGLE_FRAME", "true")
    live_root = tmp_path / "live"
    godown = "GDN_001"
    camera = "CAM_01"
    base = time.time()

    latest = live_root / godown / f"{camera}_latest.jpg"
    _write_file(latest, b"latest", mtime=base + 10)
    _write_file(live_root / godown / f"{camera}_1700000000.jpg", b"old-1", mtime=base + 1)
    _write_file(live_root / godown / f"{camera}_1700000001.jpg", b"old-2", mtime=base + 2)
    _write_file(live_root / godown / f"OTHER_latest.jpg", b"other", mtime=base + 3)

    resolved = enforce_single_live_frame(live_root, godown, camera, cleanup_every_sec=0.0)

    assert resolved == latest
    assert latest.exists()
    assert (live_root / godown / f"{camera}_1700000000.jpg").exists() is False
    assert (live_root / godown / f"{camera}_1700000001.jpg").exists() is False
    assert (live_root / godown / "OTHER_latest.jpg").exists()


def test_enforce_single_live_frame_promotes_newest_when_latest_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PDS_LIVE_ENFORCE_SINGLE_FRAME", "true")
    live_root = tmp_path / "live"
    godown = "GDN_001"
    camera = "CAM_01"
    base = time.time()

    older = live_root / godown / f"{camera}_legacy_a.jpg"
    newer = live_root / godown / f"{camera}_legacy_b.jpg"
    _write_file(older, b"older", mtime=base + 1)
    _write_file(newer, b"newer", mtime=base + 5)

    latest = enforce_single_live_frame(live_root, godown, camera, cleanup_every_sec=0.0)

    assert latest == (live_root / godown / f"{camera}_latest.jpg")
    assert latest.exists()
    assert latest.read_bytes() == b"newer"
    assert older.exists() is False
    assert newer.exists() is False


def test_remove_live_frame_artifacts_cleans_latest_and_legacy(tmp_path: Path) -> None:
    live_root = tmp_path / "live"
    godown = "GDN_001"
    camera = "CAM_01"

    latest = live_root / godown / f"{camera}_latest.jpg"
    legacy = live_root / godown / f"{camera}_legacy.jpg"
    subdir_frame = live_root / godown / camera / "frame_1.jpg"

    _write_file(latest, b"latest")
    _write_file(legacy, b"legacy")
    _write_file(subdir_frame, b"subdir")

    remove_live_frame_artifacts(live_root, godown, camera, include_latest=True, include_subdirs=True)

    assert latest.exists() is False
    assert legacy.exists() is False
    assert subdir_frame.exists() is False
