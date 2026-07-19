from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pytest

from src.analytics.adapters.p1_outputs import P1OutputError, load_accepted_p1_contacts


FIXTURE = Path("tests/fixtures/integration/p1_analytics_accepted")


def _copy(tmp_path: Path) -> Path:
    target = tmp_path / "p1"
    shutil.copytree(FIXTURE, target)
    return target


def _json(path: Path) -> object:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload) + "\n")


def _mutate_csv(path: Path, mutate) -> None:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = reader.fieldnames
    mutate(rows)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_loads_five_real_contacts_with_vfr_timestamps_and_deterministic_order() -> None:
    first = load_accepted_p1_contacts(FIXTURE)
    second = load_accepted_p1_contacts(FIXTURE)

    assert [item.event.event_id for item in first] == ["ev_001", "ev_003", "ev_005", "ev_007", "ev_009"]
    assert [item.event.timestamp_seconds for item in first] == [2.771667, 3.955, 5.688333, 6.971667, 8.638333]
    assert first == second
    assert all(len(item.pose["keypoints"]) == 133 for item in first)
    assert [item.player.identity for item in first] == ["near", "far", "near", "far", "near"]


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("duplicate_event", "duplicate or empty event_id"),
        ("missing_track", "missing track"),
        ("mismatched_identity", "mismatched identity"),
        ("contact_track_mismatch", "contact-to-track mismatch"),
        ("missing_pose", "missing pose"),
        ("bad_keypoints", "exactly 133 keypoints"),
        ("missing_position", "missing court position"),
        ("invalid_confidence", r"confidence must be finite in \[0,1\]"),
    ],
)
def test_rejects_inconsistent_serialized_p1_inputs(tmp_path: Path, case: str, message: str) -> None:
    target = _copy(tmp_path)
    contacts_path = target / "selected_contact_audit.json"
    contacts = _json(contacts_path)
    assert isinstance(contacts, list)

    if case == "duplicate_event":
        contacts[1]["event_id"] = contacts[0]["event_id"]
        _write_json(contacts_path, contacts)
    elif case == "missing_track":
        contacts[0]["track_id"] = "track_missing"
        _write_json(contacts_path, contacts)
    elif case == "mismatched_identity":
        contacts[0]["expected_player"] = "far"
        _write_json(contacts_path, contacts)
    elif case == "contact_track_mismatch":
        _mutate_csv(target / "selected_player_tracks.csv", lambda rows: rows[0].update(selected_identity="far", identity="far"))
    elif case in {"missing_pose", "bad_keypoints"}:
        pose_path = target / "selected_player_pose.jsonl"
        rows = [json.loads(line) for line in pose_path.read_text().splitlines()]
        if case == "missing_pose":
            rows.pop(0)
        else:
            rows[0]["keypoints"].pop()
        pose_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    elif case == "missing_position":
        _mutate_csv(target / "selected_player_court_positions.csv", lambda rows: rows.pop(0))
    else:
        contacts[0]["confidence"] = 1.1
        _write_json(contacts_path, contacts)

    with pytest.raises(P1OutputError, match=message):
        load_accepted_p1_contacts(target)


def test_analytics_package_does_not_import_player_perception() -> None:
    sources = Path("src/analytics").rglob("*.py")
    assert all("src.player_perception" not in path.read_text() for path in sources)
