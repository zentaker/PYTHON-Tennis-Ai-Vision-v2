from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.analytics.adapters.p1_outputs import load_accepted_p1_contacts
from src.analytics.p1_wiring import (
    Stage4InputError,
    load_stage4,
    wire_contacts,
    write_wiring_outputs,
)
from src.analytics.schema_validation import validators


FIXTURE = Path("tests/fixtures/integration/p1_analytics_accepted")
SOURCE_SHA = "ec24ac0f34f787b6b86258076186c7f90c2b2c4e"
RESULTS_SHA = "a2e2c138cff1076b9531c24d690a48a44b993a8168e3b52a5d274a50ed11feba"


def _stage4_file(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "stage4.json"
    path.write_text(json.dumps(payload) + "\n")
    return path


@pytest.mark.parametrize(
    "payload",
    [
        [{"id": "ev_001", "shot_type": "saque"}],
        {"events": [{"event_id": "ev_001", "shot_type": "saque"}]},
        {"narrative_events": [{"id": "ev_001", "shot_type": "saque"}]},
    ],
)
def test_load_stage4_accepts_only_supported_shapes(tmp_path: Path, payload: object) -> None:
    assert load_stage4(_stage4_file(tmp_path, payload))["ev_001"]["shot_type"] == "saque"


def test_load_stage4_is_optional() -> None:
    assert load_stage4(None) == {}


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (42, "JSON root must be a list or object"),
        ({"metadata": []}, "requires 'events' or 'narrative_events'"),
        ({"events": {}}, "'events' must be a list"),
        ({"events": ["ev_001"]}, "event index 0 must be an object"),
        ({"events": [{"shot_type": "saque"}]}, "event index 0 requires string id"),
        ({"events": [{"id": "  "}]}, "event index 0 has empty ID"),
        (
            {"events": [{"id": "ev_001"}, {"id": "ev_001"}]},
            "event index 1 has duplicate ID 'ev_001'",
        ),
        (
            {"events": [{"id": "ev_001"}, {"event_id": "ev_001"}]},
            "event index 1 has duplicate ID 'ev_001'",
        ),
        (
            {"events": [{"id": "ev_001", "event_id": "ev_003"}]},
            "event index 0 has conflicting id 'ev_001' and event_id 'ev_003'",
        ),
    ],
)
def test_load_stage4_fails_closed(
    tmp_path: Path, payload: object, message: str
) -> None:
    path = _stage4_file(tmp_path, payload)
    with pytest.raises(Stage4InputError, match=message):
        load_stage4(path)


def test_load_stage4_rejects_invalid_json_root(tmp_path: Path) -> None:
    path = tmp_path / "stage4.json"
    path.write_text("{")
    with pytest.raises(Stage4InputError, match=r"stage4\.json: invalid JSON root"):
        load_stage4(path)


def test_wires_exactly_five_conservative_schema_valid_records() -> None:
    contacts = load_accepted_p1_contacts(FIXTURE)
    records = wire_contacts(
        contacts,
        load_stage4(FIXTURE / "stage4_events.json"),
        p1_source_sha=SOURCE_SHA,
        p1_results_sha256=RESULTS_SHA,
    )
    _, validator = validators()

    assert len(records) == 5
    serialized = [record.to_dict() for record in records]
    for record in serialized:
        validator.validate(record)
        assert record["kinematics"] is None
        assert record["stroke"]["hitting_hand"]["value"] == "unknown"
        assert record["event"]["metadata"]["stage5b_xyz_status"] == "APPROVED_STAGE5B_XYZ_REQUIRED"
        evidence = record["evidence"]
        assert len([item for item in evidence if item["source"] == "stage5b_xyz"]) == 1
        assert next(item for item in evidence if item["source"] == "p1_court_position")["geometry_derived"]

    assert serialized[0]["event"]["legacy_shot_type"] == "saque"
    assert serialized[0]["stroke"]["stroke_side"]["value"] == "serve"
    assert serialized[0]["stroke"]["contact_mode"]["value"] == "serve"
    stage4 = next(item for item in serialized[0]["evidence"] if item["source"] == "stage4_manual_annotation")
    assert stage4["human_labeled"] and not stage4["model_inferred"] and not stage4["geometry_derived"]
    assert all(record["event"]["legacy_shot_type"] is None for record in serialized[1:])
    assert all(
        dimension["value"] == "unknown"
        for record in serialized[1:]
        for dimension in record["stroke"].values()
    )


def test_missing_and_ambiguous_stage4_labels_remain_conservative() -> None:
    contacts = load_accepted_p1_contacts(FIXTURE)
    missing = wire_contacts(contacts, {}, p1_source_sha=SOURCE_SHA, p1_results_sha256=RESULTS_SHA)
    assert all(record.event.legacy_shot_type is None for record in missing)
    assert all(record.stroke.hitting_hand.value == "unknown" for record in missing)

    ambiguous = wire_contacts(
        contacts,
        {"ev_001": {"id": "ev_001", "shot_type": "slice"}},
        p1_source_sha=SOURCE_SHA,
        p1_results_sha256=RESULTS_SHA,
    )[0]
    assert ambiguous.stroke.spin_family.value == "slice"
    assert ambiguous.stroke.stroke_side.value == "unknown"
    assert ambiguous.stroke.contact_mode.value == "unknown"


@pytest.mark.parametrize("event", [{"id": "ev_001", "shot_type": "unknown"}, {"id": "ev_001"}])
def test_unknown_or_absent_stage4_label_keeps_all_dimensions_unknown(event: dict[str, str]) -> None:
    record = wire_contacts(
        load_accepted_p1_contacts(FIXTURE),
        {"ev_001": event},
        p1_source_sha=SOURCE_SHA,
        p1_results_sha256=RESULTS_SHA,
    )[0].to_dict()
    assert record["event"]["legacy_shot_type"] is None
    assert all(dimension["value"] == "unknown" for dimension in record["stroke"].values())


def test_outputs_and_checksum_are_reproducible(tmp_path: Path) -> None:
    kwargs = {
        "p1_source_sha": SOURCE_SHA,
        "p1_results_sha256": RESULTS_SHA,
    }
    first_dir, second_dir = tmp_path / "first", tmp_path / "second"
    first = write_wiring_outputs(FIXTURE, FIXTURE / "stage4_events.json", first_dir, **kwargs)
    second = write_wiring_outputs(FIXTURE, FIXTURE / "stage4_events.json", second_dir, **kwargs)

    assert first["status"] == "P1_ANALYTICS_FUNCTIONAL_WIRING_PASSED"
    assert first["contacts_found"] == first["records_produced"] == first["schema_valid_records"] == 5
    assert first["stage4_labels_matched"] == 1
    assert first["stage4_labels_unavailable"] == 4
    assert first["unknown_stroke_dimensions"] == 23
    assert first["deterministic_output_checksum"] == second["deterministic_output_checksum"]
    assert (first_dir / "stroke_analytics_records.jsonl").read_bytes() == (second_dir / "stroke_analytics_records.jsonl").read_bytes()
    assert len((first_dir / "stroke_analytics_records.jsonl").read_text().splitlines()) == 5
    assert json.loads((first_dir / "p1_analytics_validation_report.json").read_text())["records_valid"] == 5
