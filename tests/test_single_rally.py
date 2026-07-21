from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pytest

from src.product.single_rally.errors import SingleRallyError
from src.product.single_rally.importer import import_single_rally
from src.product.single_rally.adapters import adapt_court_map
from src.product.single_rally.validation import _validate_court_semantics
from src.product.single_rally.validation import validate_single_rally_bundle
from src.product.cli import main

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/product/single_rally_v1"


def _inputs(tmp_path: Path) -> Path:
    source_dir = tmp_path / "inputs"
    source_dir.mkdir()
    for name in ("events.json", "ball_track.csv", "court_map.json"):
        shutil.copy2(FIXTURE / name, source_dir / name)
    descriptor = json.loads((FIXTURE / "single-rally-inputs.json").read_text())
    path = tmp_path / "single-rally-inputs.json"
    path.write_text(
        json.dumps(
            {
                **descriptor,
                "files": {key: f"inputs/{value}" for key, value in descriptor["files"].items()},
            }
        )
    )
    return path


def _source(tmp_path: Path) -> Path:
    path = tmp_path / "rally.mp4"
    path.write_bytes(b"synthetic_contract_fixture")
    return path


def test_import_one_rally_and_validate_deterministically(tmp_path: Path) -> None:
    source, descriptor = _source(tmp_path), _inputs(tmp_path)
    first = import_single_rally(
        source,
        descriptor,
        "session_1",
        "rally_1",
        "STANDARD",
        "clay",
        tmp_path / "first",
        "2026-07-20T00:00:00Z",
    )
    second = import_single_rally(
        source,
        descriptor,
        "session_1",
        "rally_1",
        "STANDARD",
        "clay",
        tmp_path / "second",
        "2026-07-20T00:00:00Z",
    )
    assert first["fingerprint"] == second["fingerprint"]
    assert validate_single_rally_bundle(tmp_path / "first")["rally_id"] == "rally_1"
    rally = json.loads((tmp_path / "first/rallies.json").read_text())["rallies"]
    assert len(rally) == 1 and rally[0]["ball_observation_count"] == 5
    assert json.loads((tmp_path / "first/session.json").read_text())["status"] == "complete"


@pytest.mark.parametrize(
    "mutation",
    [
        "event_outside",
        "track_outside",
        "unordered_track",
        "duplicate_event",
    ],
)
def test_input_integrity_rejections(tmp_path: Path, mutation: str) -> None:
    descriptor = _inputs(tmp_path)
    events_path = tmp_path / "inputs/events.json"
    track_path = tmp_path / "inputs/ball_track.csv"
    if mutation == "event_outside":
        payload = json.loads(events_path.read_text())
        payload["narrative_events"][0]["time_start_seconds"] = 0.01
        events_path.write_text(json.dumps(payload))
    elif mutation == "track_outside":
        rows = list(csv.DictReader(track_path.open()))
        rows[0]["timestamp_seconds"] = "0.01"
        with track_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    elif mutation == "unordered_track":
        rows = list(csv.DictReader(track_path.open()))
        rows[1]["frame_id"], rows[2]["frame_id"] = rows[2]["frame_id"], rows[1]["frame_id"]
        with track_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    else:
        payload = json.loads(events_path.read_text())
        payload["narrative_events"][1]["id"] = payload["narrative_events"][0]["id"]
        events_path.write_text(json.dumps(payload))
    with pytest.raises(SingleRallyError):
        import_single_rally(
            _source(tmp_path),
            descriptor,
            "session_1",
            "rally_1",
            "STANDARD",
            "clay",
            tmp_path / "out",
            "2026-07-20T00:00:00Z",
        )


def test_unknown_event_player_and_provenance_are_preserved(tmp_path: Path) -> None:
    descriptor = _inputs(tmp_path)
    events_path = tmp_path / "inputs/events.json"
    payload = json.loads(events_path.read_text())
    payload["narrative_events"][0]["player"] = "unknown"
    payload["narrative_events"][0]["source"] = "manual_annotation"
    events_path.write_text(json.dumps(payload))
    import_single_rally(
        _source(tmp_path),
        descriptor,
        "session_1",
        "rally_1",
        "STANDARD",
        "clay",
        tmp_path / "out",
        "2026-07-20T00:00:00Z",
    )
    event = json.loads((tmp_path / "out/events.jsonl").read_text().splitlines()[0])
    assert event["player"] == "unknown"
    assert event["provenance"]["source"] == "manual_annotation"


def test_written_count_mismatch_is_rejected(tmp_path: Path) -> None:
    descriptor = _inputs(tmp_path)
    output = tmp_path / "out"
    import_single_rally(
        _source(tmp_path),
        descriptor,
        "session_1",
        "rally_1",
        "STANDARD",
        "clay",
        output,
        "2026-07-20T00:00:00Z",
    )
    path = output / "rallies.json"
    value = json.loads(path.read_text())
    value["rallies"][0]["event_count"] += 1
    path.write_text(json.dumps(value))
    with pytest.raises(Exception, match="checksum|size|count"):
        validate_single_rally_bundle(output)


def test_single_rally_package_has_no_heavy_model_imports() -> None:
    package = "\n".join(
        path.read_text() for path in (ROOT / "src/product/single_rally").glob("*.py")
    )
    assert "torch" not in package
    assert "ultralytics" not in package


@pytest.mark.parametrize("case", ["outside", "shape", "nan", "zero_dimensions"])
def test_court_geometry_rejections(tmp_path: Path, case: str) -> None:
    path = tmp_path / "court.json"
    value = json.loads((FIXTURE / "court_map.json").read_text())
    if case == "outside":
        value["court_corners_pixel"]["far_left"] = [-1, 0]
    elif case == "shape":
        value["H_pixel_to_court"] = [[1, 0], [0, 1]]
    elif case == "nan":
        value["H_pixel_to_court"][0][0] = float("nan")
    else:
        value["frame_dimensions"]["width"] = 0
    path.write_text(json.dumps(value))
    with pytest.raises(SingleRallyError):
        adapt_court_map(path, "session_1")


def test_court_semantics_reject_unsafe_statuses(tmp_path: Path) -> None:
    court = adapt_court_map(FIXTURE / "court_map.json", "session_1")
    court["calibration_status"] = "approved"
    with pytest.raises(SingleRallyError):
        _validate_court_semantics(court)
    court["calibration_status"] = "synthetic"
    court["limitations"] = []
    with pytest.raises(SingleRallyError):
        _validate_court_semantics(court)
    court["limitations"] = ["synthetic_calibration_not_product_evidence"]
    court["homography_pixel_to_court"] = None
    court["calibration_status"] = "approved"
    court["provenance"] = "existing_court_calibration"
    with pytest.raises(SingleRallyError):
        _validate_court_semantics(court)


def test_import_hashes_source_streaming(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    descriptor = _inputs(tmp_path)
    source = _source(tmp_path)
    source.write_bytes(b"x" * (2 * 1024 * 1024))

    def fail_read_bytes(_self: Path) -> bytes:
        raise AssertionError("source video must be hashed through streaming helper")

    monkeypatch.setattr(Path, "read_bytes", fail_read_bytes)
    result = import_single_rally(
        source,
        descriptor,
        "session_1",
        "rally_1",
        "STANDARD",
        "clay",
        tmp_path / "stream",
        "2026-07-20T00:00:00Z",
    )
    assert len(result["source_sha256"]) == 64


def test_rally_cli_exit_codes(tmp_path: Path) -> None:
    descriptor = _inputs(tmp_path)
    output = tmp_path / "cli-out"
    assert (
        main(
            [
                "rally",
                "import",
                "--source-video",
                str(_source(tmp_path)),
                "--inputs",
                str(descriptor),
                "--session-id",
                "session_1",
                "--rally-id",
                "rally_1",
                "--profile",
                "STANDARD",
                "--surface",
                "clay",
                "--output",
                str(output),
                "--created-at",
                "2026-07-20T00:00:00Z",
                "--json",
            ]
        )
        == 0
    )
    assert main(["rally", "validate", "--bundle", str(output), "--json"]) == 0
    assert main(["rally", "validate", "--bundle", str(tmp_path / "missing")]) == 2
