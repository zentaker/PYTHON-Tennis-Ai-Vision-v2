from __future__ import annotations

import json
from pathlib import Path

from src.product.single_rally.validation import validate_single_rally_bundle

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/product/real_single_rally_nivel_a2_01"
VIDEO_SHA = "e2a05a8eda9be4d821ae1acc60355c7c0403e450ac0febd6bb3c6a62e0aa5774"


def _json(name: str):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def test_real_candidate_bundle_is_valid_and_external() -> None:
    result = validate_single_rally_bundle(FIXTURE)
    manifest = _json("manifest.json")
    session = _json("session.json")
    rallies = _json("rallies.json")
    assert result["session_id"] == "nivel_a2_01"
    assert manifest["source_video"]["sha256"] == VIDEO_SHA
    assert manifest["source_video"]["storage"] == "external"
    assert session["status"] == "partial"
    assert rallies["status"] == "partial"
    assert len(rallies["rallies"]) == 1
    assert rallies["rallies"][0]["status"] == "partial"


def test_real_candidate_counts_and_timestamps() -> None:
    rally = _json("rallies.json")["rallies"][0]
    events = [json.loads(line) for line in (FIXTURE / "events.jsonl").read_text().splitlines()]
    track = [json.loads(line) for line in (FIXTURE / "ball_track.jsonl").read_text().splitlines()]
    assert rally["event_count"] == len(events) == 10
    assert rally["ball_observation_count"] == len(track) == 527
    assert rally["contact_count"] == 4
    assert rally["bounce_count"] == 5
    assert all(
        rally["start_time_seconds"] <= item["timestamp_seconds"] <= rally["end_time_seconds"]
        for item in events + track
    )
    assert [item["frame_id"] for item in track] == list(range(527))
    assert all(
        0 <= item["pixel_x"] < 2746 and 0 <= item["pixel_y"] < 1536
        for item in track
        if item["visible"]
    )


def test_real_candidate_calibration_and_reports_are_non_synthetic() -> None:
    court = _json("court_map.json")
    reference = _json("REFERENCE_SOURCE.json")
    alignment = _json("alignment-report.json")
    validation = _json("validation-report.json")
    assert court["calibration_status"] == "approved"
    assert court["provenance"] != "synthetic_contract_fixture"
    assert court["coordinate_system"] == "image_pixels"
    assert court["court_coordinate_system"] == "court_meters"
    assert court["homography_pixel_to_court"]
    assert reference["asset_alignment_gate"] == "REAL_REFERENCE_ASSET_ALIGNMENT_PASSED"
    assert reference["surface"] == "unknown"
    assert alignment["video_sha_verified"] is True
    assert validation["fingerprint"] == _json("manifest.json")["bundle_fingerprint"]
    for path in FIXTURE.rglob("*"):
        if path.is_file():
            text = path.read_text(errors="ignore")
            assert "/Users/" not in text
            assert "synthetic_contract_fixture" not in text


def test_real_candidate_evidence_files_exist() -> None:
    for name in (
        "alignment-report.json",
        "validation-report.json",
        "track-court-preview.svg",
        "event-timeline.svg",
    ):
        assert (FIXTURE / name).is_file()


def test_real_candidate_contains_no_video_or_model_artifacts() -> None:
    forbidden = {".mp4", ".mov", ".mkv", ".avi", ".pt", ".pth", ".onnx", ".engine"}
    assert all(path.suffix.lower() not in forbidden for path in FIXTURE.rglob("*"))
    builder = (ROOT / "scripts/build_stage1b_real_candidate.py").read_text(encoding="utf-8")
    assert "torch" not in builder.lower()
    assert "ultralytics" not in builder.lower()
