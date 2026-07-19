#!/usr/bin/env python3
"""Branch-agnostic active checker for the Stage 5B v3 candidate."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.stage5b_v3.reconstruction import reconstruct  # noqa: E402

STATUS = "STAGE5B_V3_REJECTED_BY_HUMAN_GATE"
RESULT = ROOT / "config/stage5b_v3/stage5b_v3_result.json"
FIXTURE = ROOT / "tests/fixtures/stage5b_v3"
P1 = ROOT / "tests/fixtures/integration/p1_analytics_accepted"


def require(value: bool, message: str) -> None:
    if not value:
        raise SystemExit(message)


def main() -> int:
    result = json.loads(RESULT.read_text())
    expected = {
        "status": STATUS,
        "input_inventory_status": "CANONICAL_INPUTS_VERIFIED",
        "contacts_consumed": 5,
        "segments_reconstructed": 9,
        "bounces_constrained": 5,
        "hypotheses_evaluated": 3,
        "negative_z_violations": 0,
        "human_visual_approval": "rejected",
        "analytics_consumes_xyz": False,
    }
    for key, value in expected.items():
        require(result.get(key) == value, f"result mismatch: {key}")
    input_manifest = json.loads((ROOT / "config/stage5b_v3/input_manifest.json").read_text())
    require(input_manifest["status"] == "CANONICAL_INPUTS_VERIFIED", "input manifest status mismatch")
    for item in input_manifest["inputs"]:
        expected_hash = item["sha256"]
        path = ROOT / item["path"]
        if expected_hash == "manifest-controlled":
            require((path / "manifest.json").is_file(), f"manifest-controlled input missing: {item['path']}")
        elif path.is_file():
            require(hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash, f"input hash mismatch: {item['path']}")
        else:
            require(item["path"].startswith(".artifacts/"), f"tracked input missing: {item['path']}")
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    for filename, expected_hash in manifest["files"].items():
        path = FIXTURE / filename
        require(path.is_file(), f"fixture missing: {filename}")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash, f"hash mismatch: {filename}")
    reconstructed = reconstruct(
        FIXTURE / "camera_model_refined.json",
        FIXTURE / "smoothed_trajectory_real.csv",
        ROOT / "data/clips/nivel_a2_01/manual_annotation.json",
        P1,
        ROOT / "config/stage5b_v3/player_aware_v1.json",
        seed=42,
        max_hypotheses=3,
    )
    schema = json.loads((ROOT / "config/stage5b_v3/player_aware_xyz.schema.json").read_text())
    validator = Draft202012Validator(schema)
    for sample in reconstructed["samples"]:
        validator.validate(sample)
        require(sample["z_m"] >= -1e-6, "negative Z sample")
        require(sample["uncertainty_z_m"] > 0, "missing sample uncertainty")
    require(len(reconstructed["contacts"]) == 5, "contact count mismatch")
    require({row["player_identity"] for row in reconstructed["contacts"]} == {"near", "far"}, "near/far identity missing")
    require(len(reconstructed["segments"]) == 9, "segment count mismatch")
    require(len(reconstructed["hypotheses"]) == 3, "hypothesis count mismatch")
    require(bool(result["deterministic_xyz_checksum"]), "historical XYZ checksum missing")
    for hypothesis in reconstructed["hypotheses"]:
        require(sum(anchor["z_m"] == 0 for anchor in hypothesis["anchors"]) == 5, "bounce constraint mismatch")
    for filename in (
        "stage5b_v3_reprojection_overlay.jpg",
        "stage5b_v3_top_view.jpg",
        "stage5b_v3_side_view.jpg",
        "stage5b_v3_contact_audit.jpg",
        "stage5b_v3_hypothesis_comparison.jpg",
    ):
        path = ROOT / "docs/validation/assets" / filename
        require(path.is_file() and 0 < path.stat().st_size < 2_000_000, f"invalid visual: {filename}")
    analytics = "\n".join(path.read_text() for path in (ROOT / "src/analytics").rglob("*.py"))
    require("stage5b_v3" not in analytics, "Analytics consumes unapproved Stage 5B v3")
    print(f"status: {STATUS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
