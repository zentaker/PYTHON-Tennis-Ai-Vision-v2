from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

import src.events.render_events_contact_sheet as contact_module
import src.events.render_events_overlay as overlay_module
import src.events.render_terminal_bounce_review as terminal_module
from src.events.render_events_contact_sheet import event_review_frames, render_events_contact_sheet
from src.events.render_events_overlay import draw_events_frame, render_events_overlay
from src.events.render_events_timeline import render_events_timeline
from src.events.render_terminal_bounce_review import (
    CONTACT_FRAME_IDS,
    REVIEW_END_FRAME,
    REVIEW_START_FRAME,
    render_terminal_bounce_contact_sheet,
    render_terminal_bounce_review,
)
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
    player: str = "near",
    side: str = "near",
) -> dict[str, object]:
    return {
        "id": event_id,
        "type": event_type,
        "player": player,
        "side": side,
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
    events = [event(f"ev_{index:03d}", start=index + 4, end=index + 4) for index in range(1, 11)]
    events[3] = event("ev_004", start=8, end=10)
    write_events(events_path, events)
    output = tmp_path / "timeline.png"

    metadata = render_events_timeline(events_path, output)

    assert metadata["event_count"] == 10
    assert metadata["point_events"] == 9
    assert metadata["multiframe_events"] == 1
    assert cv2.imread(str(output)) is not None


def test_contact_sheet_uses_five_unique_context_frames_for_point_event() -> None:
    selection = event_review_frames(event(start=5, end=5), 20)

    assert [frame_id for _role, frame_id in selection] == [3, 4, 5, 6, 7]
    assert len({frame_id for _role, frame_id in selection}) == 5


def test_contact_sheet_renders_one_section_per_event(monkeypatch, tmp_path: Path) -> None:
    events = [event(f"ev_{index:03d}", start=index + 4, end=index + 4) for index in range(1, 11)]
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

    assert metadata["event_sections"] == 10
    assert [section["event_id"] for section in metadata["sections"]] == [
        f"ev_{index:03d}" for index in range(1, 11)
    ]
    image = cv2.imread(str(output))
    assert image is not None
    assert image.shape[1] == 1800


def terminal_events() -> list[dict[str, object]]:
    return [
        event("ev_009", event_type="hit", start=434, end=435),
        event(
            "ev_010",
            event_type="bounce",
            start=463,
            end=463,
            player="unknown",
            side="far",
        ),
    ]


def test_terminal_review_contains_final_hit_bounce_and_vfr_window(
    monkeypatch, tmp_path: Path
) -> None:
    events_path = tmp_path / "events.json"
    write_events(events_path, terminal_events())
    video = tmp_path / "source.mp4"
    video.touch()
    frame = np.zeros((32, 64, 3), dtype=np.uint8)
    timestamps = [index * 0.02 for index in range(527)]
    records = [
        CanonicalFrame(frame_id=index, timestamp_seconds=timestamps[index], image_bgr=frame)
        for index in range(527)
    ]
    monkeypatch.setattr(terminal_module, "iter_canonical_frames", lambda *_args, **_kwargs: records)
    captured: dict[str, object] = {}

    def fake_render(frames, _output, draw_frame, **kwargs):
        decoded = list(frames)
        captured["ids"] = [record.frame_id for record in decoded]
        captured.update(kwargs)
        terminal_relative_id = 463 - REVIEW_START_FRAME
        assert np.count_nonzero(draw_frame(decoded[terminal_relative_id])) > 0
        return {
            "frames": len(decoded),
            "width": 2746,
            "height": 1536,
            "duration_seconds": 1.04,
        }

    monkeypatch.setattr(terminal_module, "render_canonical_vfr_overlay", fake_render)
    metadata = render_terminal_bounce_review(
        video,
        manifest(),
        timestamps,
        events_path,
        tmp_path / "review.mp4",
    )

    assert captured["ids"] == list(range(REVIEW_END_FRAME - REVIEW_START_FRAME + 1))
    assert metadata["source_frame_start"] <= 434
    assert metadata["source_frame_end"] >= 463
    assert metadata["includes_final_hit"] is True
    assert metadata["includes_terminal_bounce"] is True


def test_terminal_contact_sheet_uses_459_to_467_and_marks_463(monkeypatch, tmp_path: Path) -> None:
    events_path = tmp_path / "events.json"
    write_events(events_path, terminal_events())
    video = tmp_path / "source.mp4"
    video.touch()
    timestamps = [index * 0.02 for index in range(527)]
    records = [
        CanonicalFrame(
            frame_id=index,
            timestamp_seconds=timestamps[index],
            image_bgr=np.full((32, 64, 3), index % 255, dtype=np.uint8),
        )
        for index in CONTACT_FRAME_IDS
    ]
    monkeypatch.setattr(terminal_module, "iter_canonical_frames", lambda *_args, **_kwargs: records)
    output = tmp_path / "terminal_contact.png"

    metadata = render_terminal_bounce_contact_sheet(
        video,
        manifest(),
        timestamps,
        events_path,
        output,
    )

    assert metadata["frames"] == list(range(459, 468))
    assert metadata["terminal_frame"] == 463
    assert metadata["event_id"] == "ev_010"
    image = cv2.imread(str(output))
    assert image is not None
    assert image.shape[1] == 1800
