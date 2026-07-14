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

    with pytest.raises(FileNotFoundError, match="manual_event_annotator"):
        load_normalized_events(missing)
