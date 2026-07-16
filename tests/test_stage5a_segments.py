"""Stage 5A A2 segment and readiness contracts."""

import json
from pathlib import Path


def test_nine_segments_and_terminal_bounce() -> None:
    path = Path("outputs/nivel_a2_01/stage_5a/flight_segments.json")
    if not path.exists():
        # Generated artifacts are ignored; this keeps a source checkout testable.
        return
    payload = json.loads(path.read_text())
    assert payload["segment_count"] == 9
    assert payload["segments"][-1]["start_event"] == "ev_009"
    assert payload["segments"][-1]["end_event"] == "ev_010"
    assert payload["segments"][-1]["end_frame"] == 463


def test_bounce_constraints_are_grounded() -> None:
    path = Path("outputs/nivel_a2_01/stage_5a/flight_segments.json")
    if not path.exists():
        return
    constraints = [c for c in json.loads(path.read_text())["unique_bounce_constraints"]]
    assert len(constraints) == 5
    assert all(c["Z_m"] == 0.0 for c in constraints)


def test_readiness_explicitly_defers_vertical_reference() -> None:
    path = Path("outputs/nivel_a2_01/stage_5a/readiness_report.json")
    if not path.exists():
        return
    report = json.loads(path.read_text())
    assert report["decision"] in {"READY_FOR_STAGE_5B", "NEEDS_VERTICAL_REFERENCE", "INSUFFICIENT_TRACKING"}
    assert report["stage_5b_started"] is False
