#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.stage5b_v3.v31 import reconstruct_v31  # noqa: E402


def require(value: bool, message: str) -> None:
    if not value:
        raise SystemExit(message)


def main() -> int:
    result = json.loads((ROOT / "config/stage5b_v3/stage5b_v31_result.json").read_text())
    require(result["status"] == "STAGE5B_V31_PARTIAL", "v3.1 status mismatch")
    require(result["human_approval"] == "pending", "human gate must remain pending")
    require(result["analytics_consumes_xyz"] is False, "Analytics must remain blocked")
    require(result["homography_used"] is True and result["racket_extension_used"] is True, "required geometry inactive")
    reconstructed = reconstruct_v31(
        ROOT / "tests/fixtures/stage5b_v3/camera_model_refined.json",
        ROOT / "data/clips/nivel_a2_01/homography.json",
        ROOT / "tests/fixtures/stage5b_v3/smoothed_trajectory_real.csv",
        ROOT / "data/clips/nivel_a2_01/manual_annotation.json",
        ROOT / "tests/fixtures/integration/p1_analytics_accepted",
        ROOT / "config/stage5b_v3/player_aware_v1.json",
        seed=42,
        starts_per_segment=3,
    )
    require(reconstructed["observations_in_objective"] == 314, "not all observations optimized")
    require(reconstructed["optimized_median_error_px"] < reconstructed["baseline_median_error_px"], "optimizer did not improve baseline")
    require(reconstructed["checksum"] == result["checksum"], "v3.1 checksum mismatch")
    schema = json.loads((ROOT / "config/stage5b_v3/player_aware_xyz.schema.json").read_text())
    validator = Draft202012Validator(schema)
    for sample in reconstructed["samples"]:
        validator.validate(sample)
        require(sample["z_m"] >= 0, "negative Z")
    require(len(reconstructed["samples"]) == 314, "schema-valid sample count mismatch")
    require(result["optimized_p95_error_px"] > 24, "PARTIAL blocker no longer present")
    require(result["contacts_physically_plausible"] is False, "far-player blocker hidden")
    for name in ("top_view", "side_view", "reprojection_contact_sheet", "contact_audit", "hypothesis_comparison", "coordinate_audit"):
        path = ROOT / f"docs/validation/assets/stage5b_v31_{name}.jpg"
        require(path.is_file() and 0 < path.stat().st_size < 2_000_000, f"invalid visual: {name}")
    print("status: STAGE5B_V31_PARTIAL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
