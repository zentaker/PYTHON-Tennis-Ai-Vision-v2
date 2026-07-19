#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
OUT = ROOT / ".artifacts/stage5b-v351-truthful-gate-a/output"


def require(value: bool, message: str) -> None:
    if not value:
        raise SystemExit(message)


def main() -> int:
    result = json.loads((OUT / "stage5b_v351_run_report.json").read_text())
    measurement = json.loads((OUT / "stage5b_v351_measurement_integrity.json").read_text())
    candidates = json.loads((OUT / "stage5b_v351_event_candidates.json").read_text())
    hypotheses = json.loads((OUT / "stage5b_v351_global_hypotheses.json").read_text())
    edges = json.loads((OUT / "stage5b_v351_edge_costs.json").read_text())
    require(json.loads((ROOT / "config/stage5b_v3/stage5b_v35_result.json").read_text())["stage5b_v35_measurement_gate"] == "STAGE5B_V35_MEASUREMENT_GATE_REJECTED", "v3.5 rejection missing")
    report = measurement["report"]
    require(report["observations_inventoried"] == 314 and report["status"] in {"STAGE5B_V351_MEASUREMENT_INTEGRITY_PASSED", "STAGE5B_V351_MEASUREMENT_INTEGRITY_PARTIAL"}, "dynamic Gate D missing")
    require(result["observations_downweighted"] > 0 and result["suspicious_observations"] > 0, "anomaly weights missing")
    require(len({row["event_id"] for row in candidates}) == 10, "event candidates missing")
    source = (ROOT / "scripts/run_stage5b_v351_truthful_gate_a.py").read_text()
    require("stage5b_v34_event_nodes" not in source, "fixed v3.4 nodes reused")
    require(len(edges) >= 9 and all(edge.get("selection_basis") != "speed_only" for edge in edges), "edge search missing")
    require(len(hypotheses) >= 2, "multiple global hypotheses missing")
    with (OUT / "stage5b_v351_frame_residuals.csv").open(newline="") as handle:
        require(sum(1 for _ in csv.DictReader(handle)) == 314, "residual rows incomplete")
    worst = json.loads((OUT / "stage5b_v351_worst_residuals.json").read_text())
    require(len(worst["worst_usable_frames"]) == 20, "worst residual report empty")
    require(result["gate_b_executed"] is False and result["human_v351_approval"] == "pending", "Gate B or human status invalid")
    require(result["analytics_consumes_xyz"] is False and result["pr_draft"] is True, "analytics/PR contract invalid")
    require(result["cloud_calls"] == result["gpu_calls"] == result["spend"] == 0, "resource use nonzero")
    for name in ("measurement_integrity", "contact_time_windows", "contact_candidate_geometry", "global_hypotheses", "reprojection_contact_sheet", "worst_reprojection_frames", "top_view", "side_view", "holdout", "per_segment_metrics"):
        path = ROOT / f"docs/validation/assets/stage5b_v351_{name}.jpg"
        require(path.is_file() and 1_000 < path.stat().st_size < 2_000_000, f"real visual missing: {name}")
    print(f"status: {result['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
