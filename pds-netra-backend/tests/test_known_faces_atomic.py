import json
import threading
from pathlib import Path

from app.core.fileio import locked_json_update, read_json_file


def _add_person(path: Path, person_id: str) -> None:
    def _update(faces: list) -> list:
        items = list(faces) if isinstance(faces, list) else []
        exists = any(isinstance(f, dict) and f.get("person_id") == person_id for f in items)
        if not exists:
            items.append(
                {
                    "person_id": person_id,
                    "name": f"Name-{person_id}",
                    "role": "STAFF",
                    "godown_id": "GDN_001",
                    "embedding": [],
                }
            )
        return items

    locked_json_update(path, _update)


def _update_person(path: Path, person_id: str) -> None:
    def _update(faces: list) -> list:
        items = list(faces) if isinstance(faces, list) else []
        for item in items:
            if isinstance(item, dict) and item.get("person_id") == person_id:
                item["name"] = f"Updated-{person_id}"
                break
        return items

    locked_json_update(path, _update)


def _delete_person(path: Path, person_id: str) -> None:
    def _update(faces: list) -> list:
        items = list(faces) if isinstance(faces, list) else []
        return [f for f in items if not isinstance(f, dict) or f.get("person_id") != person_id]

    locked_json_update(path, _update)


def test_locked_json_update_concurrency(tmp_path: Path):
    path = tmp_path / "known_faces.json"

    def _worker(idx: int) -> None:
        pid = f"P{idx}"
        for _ in range(10):
            _add_person(path, pid)
            _update_person(path, pid)
            if idx % 5 == 0:
                _delete_person(path, pid)
                _add_person(path, pid)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # File must be valid JSON and contain no duplicate person_id
    data = read_json_file(path, [])
    assert isinstance(data, list)
    seen = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        pid = item.get("person_id")
        assert pid not in seen
        seen.add(pid)

    # Also ensure file is parseable via json.load for corruption check
    assert json.loads(path.read_text(encoding="utf-8")) == data
