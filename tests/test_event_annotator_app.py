from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from src.events.event_loader import load_normalized_events
from tools.event_annotator_app.core import (
    AnnotatorError,
    EventStore,
    FrameIndex,
    FrameRecord,
    NavigationState,
    load_tracking,
)
from tools.event_annotator_app.server import create_server


def make_index(tmp_path: Path, count: int = 527) -> FrameIndex:
    frames = tmp_path / "frames"
    frames.mkdir(parents=True)
    records = []
    for frame_id in range(count):
        relative = f"frames/frame_{frame_id:06d}.webp"
        (tmp_path / relative).write_bytes(f"frame-{frame_id}".encode())
        records.append(
            FrameRecord(
                frame_id=frame_id,
                timestamp_seconds=frame_id * 0.02,
                duration_seconds=0.02,
                cache_path=relative,
                image_sha256=f"{frame_id:064x}",
                duplicate_visual_content=False,
            )
        )
    return FrameIndex(
        cache_dir=tmp_path,
        video_sha256="a" * 64,
        clip_id="nivel_a2_01",
        width=2746,
        height=1536,
        duration_seconds=count * 0.02,
        records=records,
    )


def make_store(tmp_path: Path, frame_index: FrameIndex) -> EventStore:
    return EventStore(
        frame_index,
        clip_id="nivel_a2_01",
        video_path=tmp_path / "source.mp4",
        draft_path=tmp_path / "annotation_draft.json",
        annotation_path=tmp_path / "manual_annotation.json",
    )


def test_frame_index_requires_exact_ids_unique_paths_and_strict_timestamps(tmp_path: Path) -> None:
    index = make_index(tmp_path)

    assert index.frame_count == 527
    assert [record.frame_id for record in index.records] == list(range(527))
    assert index.image_path(11).name == "frame_000011.webp"
    assert index.image_path(12).name == "frame_000012.webp"
    assert index.image_path(11) != index.image_path(12)


@pytest.mark.parametrize("frame_id", [-1, 527, True, 1.5])
def test_frame_index_rejects_invalid_bounds_and_types(tmp_path: Path, frame_id: object) -> None:
    index = make_index(tmp_path)

    with pytest.raises(AnnotatorError):
        index.record(frame_id)  # type: ignore[arg-type]


def test_visual_duplicates_keep_distinct_ids_and_paths(tmp_path: Path) -> None:
    frames = tmp_path / "frames"
    frames.mkdir()
    records = []
    for frame_id in range(3):
        path = frames / f"frame_{frame_id:06d}.webp"
        path.write_bytes(b"same visual")
        records.append(
            FrameRecord(
                frame_id=frame_id,
                timestamp_seconds=frame_id * 0.02,
                duration_seconds=0.02,
                cache_path=f"frames/{path.name}",
                image_sha256="f" * 64,
                duplicate_visual_content=True,
            )
        )

    index = FrameIndex(
        cache_dir=tmp_path,
        video_sha256="a" * 64,
        clip_id="test",
        width=10,
        height=10,
        duration_seconds=0.06,
        records=records,
    )

    assert [record.frame_id for record in index.records] == [0, 1, 2]
    assert len({record.cache_path for record in index.records}) == 3
    assert all(record.duplicate_visual_content for record in index.records)


def test_navigation_sequences_forward_reverse_and_hundred_steps(tmp_path: Path) -> None:
    index = make_index(tmp_path)
    navigator = NavigationState(index)

    assert [navigator.current, navigator.move(1), navigator.move(1), navigator.move(-1)] == [
        0,
        1,
        2,
        1,
    ]
    navigator.jump(10)
    assert [navigator.current, *[navigator.move(delta) for delta in [1, 1, 1, -1, -1, -1]]] == [
        10,
        11,
        12,
        13,
        12,
        11,
        10,
    ]
    navigator.jump(0)
    for _ in range(100):
        navigator.move(1)
    assert navigator.current == 100
    for _ in range(100):
        navigator.move(-1)
    assert navigator.current == 0


@pytest.mark.parametrize(("start", "end"), [(40, 40), (40, 41), (40, 42), (132, 134)])
def test_event_store_creates_point_and_multiframe_ranges(
    tmp_path: Path, start: int, end: int
) -> None:
    store = make_store(tmp_path, make_index(tmp_path / "cache"))

    event = store.create({"preset": "hit_near", "frame_start": start, "frame_end": end})

    assert event["frame_start"] == start
    assert event["frame_end"] == end
    assert event["frame_range"] == [start, end]
    assert event["time_start_seconds"] == pytest.approx(start * 0.02)
    assert event["time_end_seconds"] == pytest.approx(end * 0.02)


def test_presets_match_stage4_product_mapping(tmp_path: Path) -> None:
    store = make_store(tmp_path, make_index(tmp_path / "cache"))

    serve = store.create({"preset": "serve_far", "frame_start": 1, "frame_end": 1})
    bounce = store.create({"preset": "bounce_near", "frame_start": 2, "frame_end": 2})

    assert (serve["type"], serve["player"], serve["side"], serve["shot_type"]) == (
        "serve",
        "far",
        "far",
        "saque",
    )
    assert (bounce["type"], bounce["player"], bounce["side"]) == (
        "bounce",
        "unknown",
        "near",
    )


def test_autosave_restore_undo_edit_delete_and_export(tmp_path: Path) -> None:
    index = make_index(tmp_path / "cache")
    store = make_store(tmp_path, index)
    first = store.create({"preset": "hit_near", "frame_start": 10, "frame_end": 10})
    second = store.create({"preset": "bounce_far", "frame_start": 20, "frame_end": 22})

    assert json.loads((tmp_path / "annotation_draft.json").read_text())["narrative_events"]
    restored = make_store(tmp_path, index)
    assert [event["id"] for event in restored.list()] == [first["id"], second["id"]]

    updated = restored.update(
        str(second["id"]),
        {"frame_start": 21, "frame_end": 23, "notes": "ambiguous impact"},
    )
    assert updated["time_start_seconds"] == pytest.approx(index.record(21).timestamp_seconds)
    assert updated["notes"] == "ambiguous impact"
    restored.delete(str(first["id"]))
    assert len(restored.list()) == 1
    assert len(restored.undo()) == 2
    assert restored.export().is_file()
    _, normalized = load_normalized_events(tmp_path / "manual_annotation.json")
    assert len(normalized) == 2


def test_export_refuses_empty_human_annotation(tmp_path: Path) -> None:
    store = make_store(tmp_path, make_index(tmp_path / "cache"))

    with pytest.raises(AnnotatorError, match="without human events"):
        store.export()


def test_optional_tracking_loads_or_remains_absent(tmp_path: Path) -> None:
    assert load_tracking(tmp_path / "missing.csv", 3) == {}
    path = tmp_path / "tracking.csv"
    path.write_text(
        "frame_id,x_smooth,y_smooth,source\n"
        "0,1.0,2.0,detected\n"
        "1,,,missing\n"
        "2,3.0,4.0,interpolated\n",
        encoding="utf-8",
    )

    tracking = load_tracking(path, 3)

    assert tracking[0] == {"x": 1.0, "y": 2.0, "source": "detected"}
    assert tracking[1]["x"] is None


class FakeSession:
    def __init__(self, tmp_path: Path) -> None:
        self.frame_index = make_index(tmp_path / "cache")
        self.ready = True
        self.self_test = {"status": "PASSED_30_30", "passed": True, "passed_count": 30, "total": 30}
        self.tracking: dict[int, dict[str, object]] = {}
        self.events = make_store(tmp_path, self.frame_index)

    def session_payload(self) -> dict[str, object]:
        return {
            "clip_id": "nivel_a2_01",
            "frame_count": 527,
            "first_frame_id": 0,
            "last_frame_id": 526,
            "width": 2746,
            "height": 1536,
            "duration_seconds": 10.54,
            "ready": True,
            "self_test_status": "PASSED_30_30",
            "tracking_available": False,
            "draft_restored": False,
            "frame_timestamps": [record.timestamp_seconds for record in self.frame_index.records],
        }

    def frame_metadata(self, frame_id: int) -> dict[str, object]:
        record = self.frame_index.record(frame_id)
        return {**record.__dict__, "tracking": None}


def request_json(url: str, method: str = "GET", payload: dict | None = None) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_http_api_serves_exact_frames_bounds_and_event_crud(tmp_path: Path) -> None:
    session = FakeSession(tmp_path)
    server = create_server(session, 0)  # type: ignore[arg-type]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, payload = request_json(f"{base}/api/session")
        assert status == 200 and payload["frame_count"] == 527
        with urllib.request.urlopen(f"{base}/api/frames/11") as response:
            assert response.read() == b"frame-11"
        with urllib.request.urlopen(f"{base}/api/frames/12") as response:
            assert response.read() == b"frame-12"
        status, metadata = request_json(f"{base}/api/frames/100/metadata")
        assert status == 200 and metadata["cache_path"] == "frames/frame_000100.webp"
        assert request_json(f"{base}/api/frames/527/metadata")[0] == 400
        assert request_json(f"{base}/api/frames/-1/metadata")[0] == 404

        status, created = request_json(
            f"{base}/api/events",
            "POST",
            {"preset": "hit_near", "frame_start": 132, "frame_end": 134},
        )
        assert status == 201
        event_id = created["event"]["id"]
        status, edited = request_json(
            f"{base}/api/events/{event_id}",
            "PATCH",
            {"frame_start": 131, "frame_end": 134, "notes": "edited"},
        )
        assert status == 200 and edited["event"]["frame_start"] == 131
        assert request_json(f"{base}/api/events/{event_id}", "DELETE")[0] == 200
        assert request_json(f"{base}/api/events/undo", "POST", {})[0] == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_frontend_contains_selection_undo_tracking_and_atomic_navigation() -> None:
    javascript = Path("tools/event_annotator_app/static/app.js").read_text(encoding="utf-8")

    assert "state.selectionStart = state.current" in javascript
    assert "state.selectionEnd = state.current" in javascript
    assert "state.selectionStart = null; state.selectionEnd = null" in javascript
    assert 'api("/api/events/undo"' in javascript
    assert "renderBallInspector" in javascript
    assert "state.loading = true" in javascript
    assert "state.current = target" in javascript
    assert (
        "await Promise.all([api(metadataUrl(target)), loadImage(frameUrl(target))])" in javascript
    )
