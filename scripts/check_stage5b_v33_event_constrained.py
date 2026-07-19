#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "config/stage5b_v3"
STATUS = "STAGE5B_V33_PHASE_A_METHOD_REJECTED"


def load(name: str):
    return json.loads((CONFIG / name).read_text())


def require(value: bool, message: str) -> None:
    if not value:
        raise SystemExit(message)


def main() -> int:
    v32 = load("stage5b_v32_result.json")
    result = load("stage5b_v33_result.json")
    timeline = load("stage5b_v33_event_timeline.json")
    topology = load("stage5b_v33_segment_topology.json")
    feasibility = load("stage5b_v33_endpoint_feasibility.json")
    objective = load("stage5b_v33_objective_breakdown.json")
    worst = load("stage5b_v33_worst_residuals.json")
    segments = load("stage5b_v33_segments.json")
    require(
        v32["stage5b_v32_human_gate"] == "STAGE5B_V32_REJECTED_BY_HUMAN_GATE", "v32 rejection lost"
    )
    require(
        v32["static_anchors_accepted"] == 5
        and v32["bounce_constraint_gate"] == "BOUNCE_CONSTRAINTS_PASSED",
        "approved evidence lost",
    )
    require(
        len(timeline) == 10
        and len(topology) == 9
        and all(row["topology_status"] == "PASS" for row in topology),
        "topology invalid",
    )
    require(
        sum(row["observations_count"] for row in topology) == 314, "observation topology mismatch"
    )
    require(
        feasibility["status"] == "PHASE_A_ENDPOINT_FEASIBILITY_FAILED"
        and not result["phase_b_executed"],
        "two-phase gate violated",
    )
    require(
        result["contact_volumes_constructed"] == 5 and feasibility["contacts_viable"] == 0,
        "contact-volume result mismatch",
    )
    require(
        not objective["contact_terms_drowned_by_observation_count"]
        and len(objective["families"]) == 3,
        "objective normalization missing",
    )
    require(
        len(worst) == 20 and all(row["physical_status"] == "CONVERGED_INVALID" for row in segments),
        "forensic evidence incomplete",
    )
    require(
        result["status"] == STATUS and result["human_v33_approval"] == "pending",
        "global gate mismatch",
    )
    require(
        not result["analytics_consumes_xyz"] and result["pr_draft"],
        "Analytics/PR contract violated",
    )
    require(
        result["cloud_calls"] == result["gpu_calls"] == result["spend"] == 0, "resource use nonzero"
    )
    source = (ROOT / "tests/test_stage5b_v33_event_constrained.py").read_text()
    require(
        "anchor_changes_reduced_optimized_endpoint" in source and "wrong_mapping" in source,
        "influence tests missing",
    )
    for name in (
        "event_timeline",
        "segment_endpoint_audit",
        "contact_volume_audit",
        "worst_reprojection_frames",
        "top_view",
        "side_view",
        "hypothesis_geometry",
        "objective_breakdown",
    ):
        path = ROOT / f"docs/validation/assets/stage5b_v33_{name}.jpg"
        require(path.is_file() and 0 < path.stat().st_size < 2_000_000, f"invalid visual: {name}")
    print(f"status: {STATUS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
