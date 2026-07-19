#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "config/stage5b_v3"


def load(name):
    return json.loads((CONFIG / name).read_text())


def require(value, message):
    if not value:
        raise SystemExit(message)


def main() -> int:
    v34 = load("stage5b_v34_result.json")
    result = load("stage5b_v35_run_report.json")
    measurement = load("stage5b_v35_measurement_integrity.json")["report"]
    edges = load("stage5b_v35_edge_costs.json")
    segments = load("stage5b_v35_segments.json")
    require(
        v34["stage5b_v34_structural_gate"] == "STAGE5B_V34_TOPOLOGY_AND_SHARED_NODE_GATE_PASSED",
        "v3.4 structural gate lost",
    )
    require(
        v34["stage5b_v34_phase_b_human_gate"] == "STAGE5B_V34_PHASE_B_REJECTED_BY_HUMAN_GATE",
        "v3.4 human rejection lost",
    )
    source = (ROOT / "scripts/run_stage5b_v35_observation_conditioned.py").read_text()
    require(
        "stage5b_v32_xyz" not in source and "/Users/" not in source,
        "old XYZ or personal path dependency",
    )
    require(
        measurement["observations_inventoried"] == 314 and measurement["event_ranges_respected"],
        "Gate D inventory failed",
    )
    require(
        result["correlated_source_groups"] == 1 and result["duplicated_frozen_observations"] == 49,
        "correlation audit failed",
    )
    require(
        len(edges) == 9
        and all(
            edge["selection_basis"] != "speed_only"
            and all(model["observation_conditioned"] for model in edge["models"])
            for edge in edges
        ),
        "observation-conditioned edge costs missing",
    )
    require(
        result["gate_a_status"] == "STAGE5B_V35_OBSERVATION_CONDITIONED_NODES_PARTIAL"
        and not result["gate_b_executed"],
        "Gate sequencing failed",
    )
    require(
        len(segments) == 9 and result["human_v35_approval"] == "pending",
        "segment/gate contract failed",
    )
    require(
        not result["analytics_consumes_xyz"] and result["pr_draft"], "Analytics/PR contract failed"
    )
    require(
        result["cloud_calls"] == result["gpu_calls"] == result["spend"] == 0, "resource use nonzero"
    )
    for name in (
        "contact_time_windows",
        "measurement_integrity",
        "body_contact_geometry",
        "edge_cost_comparison",
        "global_hypotheses",
        "reprojection_contact_sheet",
        "worst_reprojection_frames",
        "top_view",
        "side_view",
        "holdout",
        "per_segment_metrics",
    ):
        path = ROOT / f"docs/validation/assets/stage5b_v35_{name}.jpg"
        require(path.is_file() and 0 < path.stat().st_size < 2_000_000, f"visual missing: {name}")
    print("status: STAGE5B_V35_MEASUREMENT_LIMITED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
