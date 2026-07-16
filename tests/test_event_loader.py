from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.events.event_loader import (
    MissingNarrativeEventsError,
    export_events,
    load_annotation,
    load_normalized_events,
    normalize_annotation,
    run_stage_4,
)
from src.events.event_schema import EventValidationError


FIXTURES = Path(__file__).parent / "fixtures"
A2_ANNOTATION = Path("data/clips/nivel_a2_01/manual_annotation.json")
A2_TIMESTAMPS = Path("data/clips/nivel_a2_01/frame_timestamps.json")


def test_valid_json_loads_in_chronological_order() -> None:
    fps, events = load_normalized_events(FIXTURES / "manual_annotation_valid.json")

    assert fps == 60.0
    assert [event.id for event in events] == ["ev_001", "ev_002", "ev_003"]
    assert [event.frame_start for event in events] == [6, 40, 70]


def test_fps_override_controls_seconds() -> None:
    fps, events = load_normalized_events(
        FIXTURES / "manual_annotation_valid.json",
        fps=30,
    )

    assert fps == 30.0
    assert events[0].time_start_seconds == pytest.approx(0.2)


def test_invalid_fixture_is_rejected() -> None:
    with pytest.raises(EventValidationError, match=r"narrative_events\[0\]"):
        load_normalized_events(FIXTURES / "manual_annotation_invalid.json")


def test_unsorted_events_are_rejected_without_reordering() -> None:
    payload = load_annotation(FIXTURES / "manual_annotation_valid.json")
    payload["narrative_events"] = list(reversed(payload["narrative_events"]))

    with pytest.raises(EventValidationError, match="chronologically"):
        normalize_annotation(payload)


def test_empty_events_block_gate_without_creating_data() -> None:
    payload = {"fps": 60, "frames_total": 120, "narrative_events": []}

    with pytest.raises(MissingNarrativeEventsError, match="cannot invent"):
        normalize_annotation(payload)


def test_event_outside_total_frames_is_rejected() -> None:
    payload = load_annotation(FIXTURES / "manual_annotation_valid.json")
    payload["frames_total"] = 50

    with pytest.raises(EventValidationError, match="outside frames_total"):
        normalize_annotation(payload)


def test_export_events_json(tmp_path: Path) -> None:
    annotation = FIXTURES / "manual_annotation_valid.json"
    fps, events = load_normalized_events(annotation)
    output = tmp_path / "events.json"

    payload = export_events(output, events, fps=fps, annotation_path=annotation)
    written = json.loads(output.read_text(encoding="utf-8"))

    assert payload["event_count"] == 3
    assert written["schema_version"] == "1.0"
    assert written["events"][1]["type"] == "bounce"
    assert written["events"][2]["time_mid_seconds"] == pytest.approx(71 / 60)


def test_run_stage_4_writes_only_after_validation(tmp_path: Path) -> None:
    output = tmp_path / "events.json"

    payload = run_stage_4(FIXTURES / "manual_annotation_valid.json", output)

    assert output.exists()
    assert payload["event_count"] == 3


def test_missing_annotation_message_names_the_manual_tool(tmp_path: Path) -> None:
    missing = tmp_path / "manual_annotation.json"

    with pytest.raises(FileNotFoundError, match="event_annotator_app"):
        load_normalized_events(missing)


def test_a2_ten_events_use_explicit_vfr_timestamps(tmp_path: Path) -> None:
    fps, events = load_normalized_events(
        A2_ANNOTATION,
        frame_timestamps_path=A2_TIMESTAMPS,
        clip_id="nivel_a2_01",
    )

    assert fps == 60.0  # Metadata only; event times come from the VFR index.
    assert len(events) == 10
    assert [event.id for event in events] == [f"ev_{index:03d}" for index in range(1, 11)]
    assert events[0].time_start_seconds == 2.771667
    assert (events[3].frame_start, events[3].frame_end) == (262, 264)
    assert (events[3].time_start_seconds, events[3].time_end_seconds) == (
        5.188333,
        5.238333,
    )
    assert (events[9].type, events[9].player, events[9].side) == (
        "bounce",
        "unknown",
        "far",
    )
    assert (events[9].frame_start, events[9].frame_end) == (463, 463)
    assert events[9].time_start_seconds == 9.221667
    assert sum(event.type == "bounce" for event in events) == 5

    output = tmp_path / "events.json"
    payload = run_stage_4(
        A2_ANNOTATION,
        output,
        frame_timestamps_path=A2_TIMESTAMPS,
        clip_id="nivel_a2_01",
    )
    assert payload["timing_mode"] == "variable_frame_rate"
    assert payload["frames_total"] == 527
    assert payload["event_count"] == 10


def test_a2_first_nine_events_remain_the_verified_sequence() -> None:
    _fps, events = load_normalized_events(
        A2_ANNOTATION,
        frame_timestamps_path=A2_TIMESTAMPS,
        clip_id="nivel_a2_01",
    )
    expected = [
        ("ev_001", "serve", "near", "near", 139, 139, 2.771667, 2.771667),
        ("ev_002", "bounce", "unknown", "far", 158, 158, 3.138333, 3.138333),
        ("ev_003", "hit", "far", "far", 200, 200, 3.955000, 3.955000),
        ("ev_004", "bounce", "unknown", "near", 262, 264, 5.188333, 5.238333),
        ("ev_005", "hit", "near", "near", 287, 288, 5.688333, 5.721667),
        ("ev_006", "bounce", "unknown", "far", 327, 327, 6.488333, 6.488333),
        ("ev_007", "hit", "far", "far", 351, 351, 6.971667, 6.971667),
        ("ev_008", "bounce", "unknown", "near", 399, 400, 7.938333, 7.955000),
        ("ev_009", "hit", "near", "near", 434, 435, 8.638333, 8.655000),
    ]

    actual = [
        (
            event.id,
            event.type,
            event.player,
            event.side,
            event.frame_start,
            event.frame_end,
            event.time_start_seconds,
            event.time_end_seconds,
        )
        for event in events[:9]
    ]
    assert actual == expected


def test_a2_loader_rejects_timestamp_not_derived_from_frame_index(tmp_path: Path) -> None:
    payload = load_annotation(A2_ANNOTATION)
    payload["narrative_events"][0]["time_start_seconds"] += 0.000001
    payload["narrative_events"][0]["time_end_seconds"] += 0.000001
    annotation = tmp_path / "changed_annotation.json"
    annotation.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EventValidationError, match="timestamps do not match"):
        load_normalized_events(
            annotation,
            frame_timestamps_path=A2_TIMESTAMPS,
            clip_id="nivel_a2_01",
        )


def test_a2_loader_rejects_duplicate_id(tmp_path: Path) -> None:
    payload = load_annotation(A2_ANNOTATION)
    payload["narrative_events"][1]["id"] = payload["narrative_events"][0]["id"]
    annotation = tmp_path / "duplicate_annotation.json"
    annotation.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EventValidationError, match="duplicate event id"):
        load_normalized_events(
            annotation,
            frame_timestamps_path=A2_TIMESTAMPS,
            clip_id="nivel_a2_01",
        )
