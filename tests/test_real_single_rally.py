from __future__ import annotations

import json
import importlib.util
from pathlib import Path

import pytest

from src.product.single_rally.validation import validate_single_rally_bundle

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/product/real_single_rally_nivel_a2_01"
VIDEO_SHA = "e2a05a8eda9be4d821ae1acc60355c7c0403e450ac0febd6bb3c6a62e0aa5774"


def _builder_module():
    spec = importlib.util.spec_from_file_location(
        "stage1b_builder", ROOT / "scripts/build_stage1b_real_candidate.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _json(name: str):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def _alignment_inputs(builder):
    video = _json("video-metadata.json")
    timestamps = _json("timestamp-audit.json")
    timestamps["frame_ids"] = list(range(527))
    track_rows = [
        json.loads(line)
        for line in (FIXTURE / "ball_track.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    track = _json("track-audit.json")
    track["frame_ids"] = [row["frame_id"] for row in track_rows]
    track["records"] = [
        {
            "frame_id": row["frame_id"],
            "timestamp_seconds": row["timestamp_seconds"],
            "source": row["source"],
            "visible": row["visible"],
            "pixel_x": row["pixel_x"],
            "pixel_y": row["pixel_y"],
        }
        for row in track_rows
    ]
    event_rows = [
        json.loads(line)
        for line in (FIXTURE / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    events = _json("event-track-alignment.json")
    events["records"] = [
        {
            "event_id": row["event_id"],
            "event_type": row["event_type"],
            "frame_id": row["frame_id"],
            "timestamp_seconds": row["timestamp_seconds"],
        }
        for row in event_rows
    ]
    events["event_ids_unique"] = True
    events["events_ordered"] = True
    events["events_in_range"] = True
    calibration = _json("calibration-audit.json")
    asset_hashes = _json("asset-hashes.json")
    clip_manifest = {
        "clip_id": "nivel_a2_01",
        "source_filename": "source.mp4",
        "source_sha256": VIDEO_SHA,
    }
    return video, timestamps, track, events, calibration, asset_hashes, clip_manifest


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
    assert reference["encoded_width"] == 1536
    assert reference["encoded_height"] == 2746
    assert reference["canonical_width"] == 2746
    assert reference["canonical_height"] == 1536
    assert reference["coordinate_space_used_by_track"] == "canonical_analysis_pixels"
    assert reference["coordinate_space_used_by_court"] == "canonical_analysis_pixels"
    assert reference["court_layout"] == "doubles"
    assert reference["surface"] == "unknown"
    assert alignment["gate_derived"] == "REAL_REFERENCE_ASSET_ALIGNMENT_PASSED"
    assert validation["fingerprint"] == _json("manifest.json")["bundle_fingerprint"]
    for path in FIXTURE.rglob("*"):
        if path.is_file():
            text = path.read_text(errors="ignore")
            assert "/Users/" not in text
            assert "synthetic_contract_fixture" not in text


def test_real_candidate_evidence_files_exist() -> None:
    for name in (
        "alignment-report.json",
        "video-metadata.json",
        "timestamp-audit.json",
        "track-audit.json",
        "event-track-alignment.json",
        "calibration-audit.json",
        "asset-hashes.json",
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


def test_alignment_gate_is_derived_and_bad_video_sha_fails() -> None:
    builder = _builder_module()
    reference = _json("REFERENCE_SOURCE.json")
    alignment = _json("alignment-report.json")
    assert alignment["gate_derived"] == "REAL_REFERENCE_ASSET_ALIGNMENT_PASSED"
    assert alignment["checks_failed"] == 0
    assert builder.EXPECTED_VIDEO_SHA != ""
    assert reference["assets"]["video"]["sha256"] == VIDEO_SHA
    assert any(check["name"] == "video_sha_expected" for check in alignment["checks"])
    inputs = _alignment_inputs(builder)
    bad = builder.evaluate_asset_alignment(*inputs, expected_video_sha="0" * 64)
    assert bad["gate_derived"] == builder.FAILED
    assert "video_sha_expected" in bad["blockers"]
    assert bad["checks_failed"] >= 1
    assert bad["video_sha_verified"] is False
    with pytest.raises(SystemExit):
        builder._require_publishable_alignment(bad)


def test_event_alignment_summary_and_preview_segments() -> None:
    alignment = _json("alignment-report.json")
    event_alignment = _json("event-track-alignment.json")
    assert event_alignment["summary"] == {
        "detected_exact": 8,
        "interpolated_exact": 2,
        "missing_exact": 0,
        "nearest_detected": 0,
        "invalid": 0,
    }
    assert event_alignment["maximum_timestamp_delta_seconds"] == 0
    assert _json("validation-report.json")["preview_segments"] > 1
    svg = (FIXTURE / "track-court-preview.svg").read_text(encoding="utf-8")
    assert svg.count("<polyline") > 1
    assert "stroke-dasharray" in svg
    assert ":hit" not in (FIXTURE / "event-timeline.svg").read_text(encoding="utf-8")
    assert alignment["references"]


def test_reported_asset_hashes_are_six_sanitized_entries() -> None:
    hashes = _json("asset-hashes.json")
    assert set(hashes) == {
        "video",
        "stage3_track",
        "frame_timestamps",
        "stage4_events",
        "court_calibration",
        "clip_manifest",
    }
    assert all(set(item) == {"display_name", "sha256"} for item in hashes.values())
    assert all("/" not in item["display_name"] for item in hashes.values())


def test_output_path_protection_rejects_external_and_root_paths(tmp_path, monkeypatch) -> None:
    builder = _builder_module()
    monkeypatch.setattr(builder, "_repo_root", lambda: tmp_path)
    artifacts = tmp_path / ".artifacts"
    artifacts.mkdir()
    with pytest.raises(SystemExit):
        builder._protected_output(tmp_path / "outside")
    with pytest.raises(SystemExit):
        builder._protected_output(artifacts)
    generated = builder._protected_output(Path("candidate"))
    assert (generated / ".stage1b-output-marker").is_file()
    assert builder._protected_output(Path("candidate")).is_dir()
    symlink = artifacts / "symlink"
    symlink.symlink_to(generated, target_is_directory=True)
    with pytest.raises(SystemExit):
        builder._protected_output(Path("symlink"))


def _publish_fixture_inputs(builder, tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "_repo_root", lambda: tmp_path)
    expected = builder._expected_fixture_path()
    expected.parent.mkdir(parents=True)
    output = tmp_path / ".artifacts" / "candidate"
    bundle = output / "build-a"
    bundle.mkdir(parents=True)
    (output / builder.MARKER).write_text("stage1b-real-single-rally-output-v1\n")
    names = (
        "manifest.json",
        "session.json",
        "rallies.json",
        "events.jsonl",
        "ball_track.jsonl",
        "court_map.json",
        "metrics.json",
        "REFERENCE_SOURCE.json",
        "alignment-report.json",
        "video-metadata.json",
        "timestamp-audit.json",
        "track-audit.json",
        "event-track-alignment.json",
        "calibration-audit.json",
        "asset-hashes.json",
        "validation-report.json",
        "track-court-preview.svg",
        "event-timeline.svg",
    )
    for name in names:
        (
            bundle
            if name
            in {
                "manifest.json",
                "session.json",
                "rallies.json",
                "events.jsonl",
                "ball_track.jsonl",
                "court_map.json",
                "metrics.json",
            }
            else output
        ).joinpath(name).write_text("{}")
    return expected, output, bundle


def test_fixture_path_is_exact_and_rejects_unsafe_variants(tmp_path, monkeypatch) -> None:
    builder = _builder_module()
    expected, _, _ = _publish_fixture_inputs(builder, tmp_path, monkeypatch)
    assert builder._protected_fixture_output(expected) == expected
    rejected = [
        tmp_path,
        tmp_path / ".git",
        tmp_path / ".artifacts",
        expected.parent,
        expected.parent.parent,
        expected.parent.parent / "other_fixture",
        tmp_path.parent / "external-fixture",
        tmp_path / "tests" / "fixtures" / "product" / ".." / "other",
    ]
    for path in rejected:
        with pytest.raises(SystemExit):
            builder._protected_fixture_output(path)
    symlink = expected.parent / "symlink-fixture"
    symlink.symlink_to(expected.parent)
    with pytest.raises(SystemExit):
        builder._protected_fixture_output(symlink)
    root2 = tmp_path / "root2"
    product_target = root2 / "real-product"
    product_target.mkdir(parents=True)
    (root2 / "tests" / "fixtures").mkdir(parents=True)
    (root2 / "tests" / "fixtures" / "product").symlink_to(product_target, target_is_directory=True)
    monkeypatch.setattr(builder, "_repo_root", lambda: root2)
    with pytest.raises(SystemExit):
        builder._protected_fixture_output(
            Path("tests/fixtures/product/real_single_rally_nivel_a2_01")
        )


def test_fixture_publication_rejects_unowned_staging_and_replaces_only_expected(
    tmp_path, monkeypatch
) -> None:
    builder = _builder_module()
    expected, output, bundle = _publish_fixture_inputs(builder, tmp_path, monkeypatch)
    staging = expected.parent / ".real_single_rally_nivel_a2_01.stage1b-staging"
    staging.mkdir()
    with pytest.raises(SystemExit):
        builder._publish_fixture(expected, output, bundle)
    staging.rmdir()
    (expected / "sentinel.txt").parent.mkdir(parents=True)
    (expected / "sentinel.txt").write_text("old")
    sibling = expected.parent / "unrelated"
    sibling.mkdir()
    (sibling / "keep.txt").write_text("keep")
    builder._publish_fixture(expected, output, bundle)
    assert not (expected / "sentinel.txt").exists()
    assert (expected / "manifest.json").is_file()
    assert (sibling / "keep.txt").read_text() == "keep"


def test_fixture_publication_rolls_back_previous_fixture_on_rename_failure(
    tmp_path, monkeypatch
) -> None:
    builder = _builder_module()
    expected, output, bundle = _publish_fixture_inputs(builder, tmp_path, monkeypatch)
    expected.mkdir(parents=True)
    (expected / "sentinel.txt").write_text("old")
    staging = expected.parent / ".real_single_rally_nivel_a2_01.stage1b-staging"
    original_rename = Path.rename

    def fail_staging_rename(self, target):
        if self == staging:
            raise OSError("simulated atomic rename failure")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_staging_rename)
    with pytest.raises(OSError):
        builder._publish_fixture(expected, output, bundle)
    assert (expected / "sentinel.txt").read_text() == "old"
    assert not staging.exists()
