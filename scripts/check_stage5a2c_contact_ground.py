#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/ground_plane_calibration"
STATUS = "CONTACT_GROUND_ANCHORS_VISUAL_AND_GEOMETRIC_GATE_PASSED"


def load(name: str) -> dict:
    return json.loads((CONFIG / name).read_text())


def require(value: bool, message: str) -> None:
    if not value:
        raise SystemExit(message)


def main() -> int:
    result = load("stage5a2c_result.json")
    lines = load("stage5a2c_line_fit_report.json")
    failures = load("stage5a2c_tracking_failures.json")
    anchors = load("stage5a2c_contact_anchor_report.json")
    uncertainty = load("stage5a2c_uncertainty.json")
    require(result["status"] == STATUS, "status mismatch")
    require(result["human_stage5a2c_approval"] == "approved_static_anchors", "human gate mismatch")
    require(
        result["contact_frame_foot_visual_gate"] == "CONTACT_FRAME_FOOT_VISUAL_GATE_PASSED",
        "contact visual gate lost",
    )
    require(
        lines["actual_line_constrained_fitting"] and lines["accepted_segments_influence_output"],
        "segments do not affect fit",
    )
    require(
        lines["accepted_segments_used_in_optimization"] == 61
        and lines["valid_calibration_families"] >= 3,
        "line families invalid",
    )
    require(
        result["sequential_tracker"]
        and result["adjacent_frame_propagation"]
        and result["bbox_updated"]
        and result["ransac_used"],
        "tracker contract invalid",
    )
    require(
        failures["invalid_frames_rejected"] > 0 and failures["invalid_spikes_excluded_from_speed"],
        "invalid drift not rejected",
    )
    require(
        anchors["anchors_produced"] == 5 and len(anchors["events"]) == 5,
        "contact anchors incomplete",
    )
    require(
        result["no_fixed_distance_cap"] and result["no_clipping"], "distance cap/clipping present"
    )
    require(result["xyz_executed"] is False and result["pr_draft"], "XYZ or PR contract violated")
    require(len(uncertainty["executed_sources"]) == 8, "uncertainty sources incomplete")
    for name in (
        "line_fit_families",
        "contact_frames",
        "local_tracking_sequences",
        "tracking_failures",
        "contact_ground_top_view",
        "far_contact_evidence",
        "uncertainty_decomposition",
    ):
        path = ROOT / f"docs/validation/assets/stage5a2c_{name}.jpg"
        require(path.is_file() and 0 < path.stat().st_size < 2_000_000, f"invalid visual: {name}")
    print(f"status: {STATUS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
