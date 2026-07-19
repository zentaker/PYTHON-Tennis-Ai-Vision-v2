#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "config/stage5b_v3"
STATUS = "STAGE5B_V32_PARTIAL"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def load(name: str) -> dict:
    return json.loads((CONFIG / name).read_text())


def main() -> int:
    result = load("stage5b_v32_result.json")
    anchors = load("stage5b_v32_anchor_v4_report.json")
    require(result["status"] == STATUS and result["human_stage5b_v32_approval"] == "pending", "gate mismatch")
    require(result["contacts_consumed"] == 5 and result["observations_consumed"] == 314, "input contract mismatch")
    require(result["observations_rejected"] == 0 and result["negative_z_violations"] == 0, "invalid filtering or Z")
    require(result["schema_valid_samples"] == 314 and len(result["checksum"]) == 64, "schema/determinism mismatch")
    require(anchors["contact_anchor_status"] == "accepted_observation" and anchors["anchors"] == 5, "anchors not accepted")
    require(not anchors["movement_added_as_measurement_uncertainty"], "motion entered uncertainty")
    require(result["pr_draft"] and not result["analytics_consumes_xyz"], "PR/Analytics contract mismatch")
    require(result["cloud_calls"] == result["gpu_calls"] == result["spend"] == 0, "nonzero resource use")
    for name in ("reprojection_contact_sheet", "top_view", "side_view", "contact_anchor_audit", "bounce_audit", "hypothesis_comparison", "uncertainty"):
        path = ROOT / f"docs/validation/assets/stage5b_v32_{name}.jpg"
        require(path.is_file() and 0 < path.stat().st_size < 2_000_000, f"invalid visual: {name}")
    print(f"status: {STATUS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
