from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

import src.events.render_events_contact_sheet as contact_module
import src.events.render_events_overlay as overlay_module
from src.events.render_events_contact_sheet import event_review_frames, render_events_contact_sheet
from src.events.render_events_overlay import draw_events_frame, render_events_overlay
from src.events.render_events_timeline import render_events_timeline
from src.project.clip_manifest import ClipManifest
from src.video.canonical_frames import CanonicalFrame


def manifest(*, frames_total: int = 527, width: int = 2746, height: int = 1536) -> ClipManifest:
    return ClipManifest.from_dict(
        {
            "clip_id": "nivel_a2_01",
            "source_filename": "source.mp4",
            "source_extension": ".mp4",
            "source_sha256": "a" * 64,
            "fps": 50.0,
            "frames_total": frames_total,
            "duration_seconds": frames_total * 0.02,
            "resolution_width": width,
            "resolution_height": height,
            "codec": "hevc",
            "camera_mode": "fixed",
            "status": "stage_2_prepared_external",
            "container_rotation_degrees": 0,
            "decoded_width": width,
            "decoded_height": height,
            "canonical_width": width,
            "canonical_height": height,
            "canonical_transform": "none",
            "timing_mode": "variable_frame_rate",
            "notes": "test",
        }
    )


def event(
    event_id: str = "ev_001",
    *,
    event_type: str = "serve",
    start: int = 5,
    end: int = 5,
) -> dict[str, object]:
    return {
        "id": event_id,
        "type": event_type,
        "player": "near",
        "side": "near",
        "shot_type": "unknown",
        "court_zone": "unknown",
        "frame_start": start,
        "frame_end": end,
        "time_start_seconds": start * 0.02,
        "time_end_seconds": end * 0.02,
    }


def write_events(path: Path, events: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({"events": events}), encoding="utf-8")


def test_draw_overlay_marks_point_start_active_and_end() -> None:
    image = np.zeros((320, 640, 3), dtype=np.uint8)
    events = [
        event("point", start=4, end=4),
        event("range", event_type="bounce", start=6, end=8),
    ]

    point = draw_events_frame(image, frame_id=4, timestamp_seconds=0.08, events=events)
    start = draw_events_frame(image, frame_id=6, timestamp_seconds=0.12, events=events)
    active = draw_events_frame(image, frame_id=7, timestamp_seconds=0.14, events=events)
    end = draw_events_frame(image, frame_id=8, timestamp_seconds=0.16, events=events)

    assert all(np.count_nonzero(frame) > 0 for frame in (point, start, active, end))
    assert not np.array_equal(point, start)
    assert not np.array_equal(start, active)
    assert not np.array_equal(active, end)


def test_stage4_overlay_dispatches_527_canonical_vfr_frames_and_last_frame(
    monkeypatch, tmp_path: Path
) -> None:
    events_path = tmp_path / "events.json"
    write_events(events_path, [event(start=139, end=139)])
    video = tmp_path / "source.mp4"
    video.touch()
    frame = np.zeros((32, 64, 3), dtype=np.uint8)
    records = [
        CanonicalFrame(frame_id=index, timestamp_seconds=index * 0.02, image_bgr=frame)
        for index in range(527)
    ]
    captured: dict[str, object] = {}
    monkeypatch.setattr(overlay_module, "iter_canonical_frames", lambda *_args, **_kwargs: records)

    def fake_render(frames, _output, draw_frame, **kwargs):
        decoded = list(frames)
        captured["count"] = len(decoded)
        captured["last"] = decoded[-1].frame_id
        captured.update(kwargs)
        assert np.count_nonzero(draw_frame(decoded[139])) > 0
        return {
            "frames": 527,
            "width": 2746,
            "height": 1536,
            "duration_seconds": 10.48,
        }

    monkeypatch.setattr(overlay_module, "render_canonical_vfr_overlay", fake_render)
    metadata = render_events_overlay(
        video,
        events_path,
        tmp_path / "overlay.mp4",
        manifest=manifest(),
        timestamps=[index * 0.02 for index in range(527)],
    )

    assert metadata["mode"] == "canonical_vfr"
    assert captured["count"] == 527
    assert captured["last"] == 526
    assert captured["expected_width"] == 2746
    assert captured["expected_height"] == 1536


def test_historical_overlay_mode_remains_available(monkeypatch, tmp_path: Path) -> None:
    video = tmp_path / "madrid.mov"
    video.touch()
    events_path = tmp_path / "events.json"
    write_events(events_path, [event()])
    expected = {"mode": "legacy_cfr", "frames": 120}
    monkeypatch.setattr(
        overlay_module,
        "_render_legacy_cfr_overlay",
        lambda *_args, **_kwargs: expected,
    )

    assert render_events_overlay(video, events_path, tmp_path / "legacy.mp4") == expected


def test_timeline_keeps_point_events_visible_and_lists_ranges(tmp_path: Path) -> None:
    events_path = tmp_path / "events.json"
    write_events(
        events_path,
        [event("ev_001", start=5, end=5), event("ev_002", start=8, end=10)],
    )
    output = tmp_path / "timeline.png"

    metadata = render_events_timeline(events_path, output)

    assert metadata["event_count"] == 2
    assert metadata["point_events"] == 1
    assert metadata["multiframe_events"] == 1
    assert cv2.imread(str(output)) is not None


def test_contact_sheet_uses_five_unique_context_frames_for_point_event() -> None:
    selection = event_review_frames(event(start=5, end=5), 20)

    assert [frame_id for _role, frame_id in selection] == [3, 4, 5, 6, 7]
    assert len({frame_id for _role, frame_id in selection}) == 5


def test_contact_sheet_renders_one_section_per_event(monkeypatch, tmp_path: Path) -> None:
    events = [event("ev_001", start=5, end=5), event("ev_002", start=8, end=10)]
    events_path = tmp_path / "events.json"
    write_events(events_path, events)
    video = tmp_path / "source.mp4"
    video.touch()
    test_manifest = manifest(frames_total=20, width=64, height=32)
    timestamps = [index * 0.02 for index in range(20)]
    frames = [
        CanonicalFrame(
            frame_id=index,
            timestamp_seconds=timestamps[index],
            image_bgr=np.full((32, 64, 3), index, dtype=np.uint8),
        )
        for index in range(20)
    ]
    monkeypatch.setattr(contact_module, "iter_canonical_frames", lambda *_args, **_kwargs: frames)
    output = tmp_path / "contact.png"

    metadata = render_events_contact_sheet(
        video,
        test_manifest,
        timestamps,
        events_path,
        output,
    )

    assert metadata["event_sections"] == 2
    assert [section["event_id"] for section in metadata["sections"]] == ["ev_001", "ev_002"]
    image = cv2.imread(str(output))
    assert image is not None
    assert image.shape[1] == 1800
