#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/ground_plane_calibration"
STATUS = "STAGE5A2B_TEMPORAL_GROUND_VALIDATION_PARTIAL"


def require(value: bool, message: str) -> None:
    if not value:
        raise SystemExit(message)


def load(name: str) -> dict:
    return json.loads((CONFIG / name).read_text())


def main() -> int:
    result = load("stage5a2b_result.json")
    lines = load("stage5a2b_line_support_report.json")
    cross = load("stage5a2b_calibration_cross_validation.json")
    players = load("stage5a2b_player_validation_report.json")
    uncertainty = load("stage5a2b_uncertainty.json")
    require(result["status"] == STATUS, "status mismatch")
    require(result["human_visual_approval"] == "pending", "human approval is not pending")
    require(result["pr_draft"] is True, "PR draft contract lost")
    require(result["xyz_executed"] is False, "Stage 5B XYZ must not execute")
    require(lines["image_line_segments_detected"] > 0, "no actual image segments")
    require(
        lines["accepted_line_segments"] > 0 and lines["rejected_line_segments"] > 0,
        "line classification incomplete",
    )
    require(lines["net_excluded_from_ground_paint_model"], "net mesh treated as ground line")
    require(
        cross["family_count"] >= 6 and cross["leave_one_family_out"], "cross-validation incomplete"
    )
    require(cross["correlated_geometry_sources"], "geometry correlation hidden")
    require(
        players["temporal_windows"] == 5 and players["temporal_frames_processed"] == 305,
        "temporal windows incomplete",
    )
    require(
        len(players["events"]) == 5 and players["identity_switches"] == 0, "event/identity mismatch"
    )
    require(players["ground_region_failures"] == 0, "contact foot outside visible ground")
    require(
        all(row["evidence_decision"] == "unresolved" for row in players["events"].values()),
        "drift blocker hidden",
    )
    require(len(uncertainty["sources"]) >= 8, "uncertainty decomposition incomplete")
    source = (ROOT / "scripts/run_stage5a2_extended_ground_plane.py").read_text()
    source_b = (ROOT / "scripts/run_stage5a2b_temporal_ground.py").read_text()
    require("/Users/" not in source and "/Users/" not in source_b, "personal path hardcoded")
    require("--temporal-radius" in source and "--strict" in source, "reproducible CLI incomplete")
    require(
        result["no_clipping"] and result["far_distance_gate_m"] is None,
        "clipping/fixed far gate present",
    )
    for name in (
        "line_segment_classification",
        "calibration_ensemble",
        "real_frame_foot_audit",
        "temporal_foot_tracks",
        "player_ground_top_view",
        "uncertainty_decomposition",
        "far_player_evidence",
    ):
        path = ROOT / f"docs/validation/assets/stage5a2b_{name}.jpg"
        require(path.is_file() and 0 < path.stat().st_size < 2_000_000, f"invalid visual: {name}")
    print(f"status: {STATUS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
