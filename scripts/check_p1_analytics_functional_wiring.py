#!/usr/bin/env python3
"""Validate the current P1-to-Analytics wiring on any branch or CI ref."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from src.analytics.p1_wiring import write_wiring_outputs  # noqa: E402


RESULT_PATH = REPOSITORY_ROOT / "config/integration/p1_analytics_functional_wiring_result.json"
FIXTURE_PATH = REPOSITORY_ROOT / "tests/fixtures/integration/p1_analytics_accepted"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def load_json(path: Path) -> object:
    require(path.is_file(), f"missing required file: {path.relative_to(REPOSITORY_ROOT)}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path.relative_to(REPOSITORY_ROOT)}: {exc}") from exc


def validate_result(result: dict[str, object]) -> None:
    expected = {
        "status": "P1_ANALYTICS_FUNCTIONAL_WIRING_PASSED",
        "p1_acceptance_status": "P1_TEN_FRAME_ACCEPTANCE_PASSED",
        "contacts_found": 5,
        "records_produced": 5,
        "events_with_real_timestamps": 5,
        "tracks_matched": 5,
        "poses_matched": 5,
        "court_positions_matched": 5,
        "wrist_evidence_matched": 5,
        "schema_valid_records": 5,
        "stage4_labels_matched": 1,
        "stage4_labels_unavailable": 4,
        "kinematics_status": "APPROVED_STAGE5B_XYZ_REQUIRED",
    }
    for field, expected_value in expected.items():
        require(result.get(field) == expected_value, f"result {field} mismatch")
    checksum = result.get("deterministic_output_checksum")
    require(isinstance(checksum, str) and bool(checksum.strip()), "result checksum is empty")


def validate_fixture() -> dict[str, object]:
    manifest_path = FIXTURE_PATH / "manifest.json"
    manifest = load_json(manifest_path)
    require(isinstance(manifest, dict), "fixture manifest root must be an object")
    files = manifest.get("files")
    require(isinstance(files, dict) and bool(files), "fixture manifest files must be non-empty")
    for filename, expected_hash in files.items():
        require(isinstance(filename, str), "fixture manifest filename must be a string")
        require(isinstance(expected_hash, str), f"fixture hash for {filename} must be a string")
        path = FIXTURE_PATH / filename
        require(path.is_file(), f"fixture file missing: {filename}")
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        require(actual_hash == expected_hash, f"fixture hash mismatch: {filename}")
    return manifest


def validate_no_package_coupling() -> None:
    analytics_root = REPOSITORY_ROOT / "src/analytics"
    for path in analytics_root.rglob("*.py"):
        source = path.read_text()
        require(
            "src.player_perception" not in source,
            f"forbidden src.player_perception import: {path.relative_to(REPOSITORY_ROOT)}",
        )


def main() -> int:
    result = load_json(RESULT_PATH)
    require(isinstance(result, dict), "functional wiring result root must be an object")
    validate_result(result)
    manifest = validate_fixture()
    validate_no_package_coupling()

    with tempfile.TemporaryDirectory(prefix="p1-analytics-wiring-") as temporary:
        report = write_wiring_outputs(
            FIXTURE_PATH,
            FIXTURE_PATH / "stage4_events.json",
            Path(temporary),
            p1_source_sha=str(manifest["source_sha"]),
            p1_results_sha256=str(manifest["source_artifact_sha256"]),
        )
    require(report["records_produced"] == 5, "reproduction did not produce five records")
    require(report["schema_valid_records"] == 5, "reproduction did not validate five records")
    require(
        report["deterministic_output_checksum"] == result["deterministic_output_checksum"],
        "reproduced output checksum mismatch",
    )
    print("status: P1_ANALYTICS_FUNCTIONAL_WIRING_VALIDATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
