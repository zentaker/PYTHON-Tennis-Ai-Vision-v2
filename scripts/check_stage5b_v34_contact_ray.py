#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "config/stage5b_v3"
STATUS = "STAGE5B_V34_PHASE_B_REJECTED_BY_HUMAN_GATE"


def load(name: str):
    return json.loads((CONFIG / name).read_text())


def require(value: bool, message: str) -> None:
    if not value:
        raise SystemExit(message)


def main() -> int:
    v33 = load("stage5b_v33_result.json")
    result = load("stage5b_v34_result.json")
    pixels = load("stage5b_v34_contact_pixel_reconciliation.json")
    rays = load("stage5b_v34_contact_ray_candidates.json")
    nodes = load("stage5b_v34_event_nodes.json")
    bounces = load("stage5b_v34_bounce_node_candidates.json")
    phase_a = load("stage5b_v34_phase_a_report.json")
    segments = load("stage5b_v34_segment_candidate_pairs.json")
    require(
        v33["stage5b_v33_topology_gate"] == "STAGE5B_V33_TOPOLOGY_GATE_PASSED", "v3.3 topology lost"
    )
    require(
        v33["stage5b_v33_phase_a_human_gate"] == "STAGE5B_V33_PHASE_A_METHOD_REJECTED",
        "v3.3 rejection lost",
    )
    source = (ROOT / "scripts/run_stage5b_v34_contact_ray_feasibility.py").read_text()
    phase_a_source = source.split("def run_phase_b", 1)[0]
    require(
        "stage5b_v32_xyz" not in phase_a_source and "/Users/" not in source,
        "forbidden dependency/path",
    )
    require(
        len(pixels) == 5 and all(row["status"] == "CONTACT_PIXEL_RECONCILED" for row in pixels),
        "pixel reconciliation failed",
    )
    require(
        len(rays) == 5
        and all(row["status"] in {"CONTACT_RAY_FEASIBLE", "CONTACT_RAY_AMBIGUOUS"} for row in rays),
        "contact rays failed",
    )
    require(
        len(nodes["nodes"]) == 10 and nodes["shared_node_consistency"] == 10, "shared nodes failed"
    )
    require(
        len(bounces) == 5 and all(row["candidate_xyz"][2] == 0 for row in bounces),
        "bounce nodes failed",
    )
    require(
        phase_a["status"] == "STAGE5B_V34_PHASE_A_PASSED"
        and all(row["feasible_pairs"] > 0 for row in segments),
        "Phase A failed",
    )
    require(
        result["phase_b_executed"] and result["observations_consumed"] == 314,
        "Phase B contract failed",
    )
    require(
        result["status"] == STATUS and result["human_v34_approval"] == "pending",
        "global gate mismatch",
    )
    require(
        not result["analytics_consumes_xyz"] and result["pr_draft"],
        "Analytics/PR contract violated",
    )
    require(
        result["cloud_calls"] == result["gpu_calls"] == result["spend"] == 0, "resource use nonzero"
    )
    for name in (
        "contact_pixel_reconciliation",
        "contact_ray_geometry",
        "event_node_graph",
        "shared_node_audit",
        "segment_feasibility",
        "top_view",
        "side_view",
        "worst_reprojection_frames",
        "hypothesis_comparison",
    ):
        path = ROOT / f"docs/validation/assets/stage5b_v34_{name}.jpg"
        require(path.is_file() and 0 < path.stat().st_size < 2_000_000, f"invalid visual: {name}")
    print(f"status: {STATUS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
