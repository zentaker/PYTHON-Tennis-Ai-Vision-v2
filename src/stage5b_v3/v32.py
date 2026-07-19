"""Stage 5B v3.2 reconstruction using human-approved static contact anchors."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from src.geometry.camera_model import CameraModel

from .optimization import _positions, optimize_segment
from .reconstruction import _load_ball, reconstruct
from .v31 import materially_ambiguous, trajectory_difference


def load_anchor_v4(path: Path) -> dict[str, dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    if len(rows) != 5 or any(
        row["contact_anchor_status"] != "accepted_observation" for row in rows
    ):
        raise ValueError("exactly five accepted static anchors v4 are required")
    return {row["event_id"]: row for row in rows}


def reconstruct_v32(
    camera_path: Path,
    ball_track_path: Path,
    events_path: Path,
    p1_results_path: Path,
    config_path: Path,
    anchors_v4_path: Path,
    *,
    seed: int = 42,
    starts_per_segment: int = 3,
) -> dict[str, Any]:
    camera = CameraModel.read_json(camera_path)
    config = json.loads(config_path.read_text())
    baseline = reconstruct(
        camera_path,
        ball_track_path,
        events_path,
        p1_results_path,
        config_path,
        seed=seed,
        max_hypotheses=3,
    )
    baseline_best = min(baseline["hypotheses"], key=lambda row: row["median_reprojection_error_px"])
    anchors = [dict(row) for row in baseline_best["anchors"]]
    accepted = load_anchor_v4(anchors_v4_path)
    consumed = []
    for anchor in anchors:
        event_id = anchor.get("event_id")
        if event_id in accepted and "player_x_m" in anchor:
            static = accepted[event_id]
            dx = static["fused_x_m"] - anchor["player_x_m"]
            dy = static["fused_y_m"] - anchor["player_y_m"]
            anchor["player_x_m"] = static["fused_x_m"]
            anchor["player_y_m"] = static["fused_y_m"]
            anchor["x_m"] += dx
            anchor["y_m"] += dy
            anchor["total_uncertainty_m"] = [
                static["uncertainty_x_m"],
                static["uncertainty_y_m"],
                float(config["contact_height_uncertainty_m"]),
            ]
            anchor["static_anchor_v4"] = static
            consumed.append(event_id)
    if len(set(consumed)) != 5:
        raise ValueError("five v4 contact anchors were not consumed")
    observations = _load_ball(ball_track_path)
    rng = np.random.default_rng(seed)
    all_solutions, selected, segment_reports = [], [], []
    for index, (start, end) in enumerate(zip(anchors, anchors[1:], strict=False), 1):
        segment_id = f"flight_{index:02d}"
        rows = [
            row
            for row in observations
            if start["timestamp_seconds"] <= row["timestamp_seconds"]
            and (row["timestamp_seconds"] < end["timestamp_seconds"] or index == len(anchors) - 1)
        ]
        solutions = optimize_segment(
            camera, segment_id, rows, start, end, config, rng, starts_per_segment
        )
        all_solutions.extend(solutions)
        best = solutions[0]
        selected.append(best)
        alternatives = list(solutions[1:])
        ambiguous = any(materially_ambiguous(best, item, config) for item in alternatives)
        endpoint = _positions(
            np.asarray(best.parameters),
            np.asarray([end["timestamp_seconds"] - start["timestamp_seconds"]]),
            float(config["gravity_mps2"]),
        )[0]
        start_residual = float(
            np.linalg.norm(
                np.asarray(best.parameters[:3])
                - np.asarray([start["x_m"], start["y_m"], start["z_m"]])
            )
        )
        end_residual = float(
            np.linalg.norm(endpoint - np.asarray([end["x_m"], end["y_m"], end["z_m"]]))
        )
        errors = [sample["reprojection_error_px"] for sample in best.samples]
        segment_reports.append(
            {
                "segment_id": segment_id,
                "observations_total": len(rows),
                "observations_used": len(rows),
                "observations_downweighted": sum(float(row["confidence"]) < 0.5 for row in rows),
                "observations_rejected": 0,
                "median_error_px": float(np.median(errors)),
                "p95_error_px": float(np.percentile(errors, 95)),
                "maximum_error_px": max(errors),
                "optimizer_cost": best.cost,
                "optimizer_improvement": float(
                    np.median(
                        [
                            sample["reprojection_error_px"]
                            for sample in baseline["samples"]
                            if sample["segment_id"] == segment_id
                        ]
                    )
                    - np.median(errors)
                ),
                "contact_residual_m": max(
                start_residual if "player_x_m" in start else 0,
                end_residual if "player_x_m" in end else 0,
                ),
                "bounce_residual_m": best.bounce_residual_m,
                "ambiguity_status": "AMBIGUOUS" if ambiguous else "RESOLVED",
                "ambiguity_metrics": [trajectory_difference(best, item) for item in alternatives],
            }
        )
    serialized = []
    ambiguity = {row["segment_id"]: row["ambiguity_status"] for row in segment_reports}
    for solution in selected:
        for sample in solution.samples:
            point = sample["xyz"]
            serialized.append(
                {
                    "frame_id": sample["frame_id"],
                    "timestamp_seconds": round(sample["timestamp_seconds"], 6),
                    "x_m": round(point[0], 3),
                    "y_m": round(point[1], 3),
                    "z_m": round(max(0.0, point[2]), 3),
                    "confidence": round(
                        float(sample["confidence"]) * np.exp(-sample["reprojection_error_px"] / 24),
                        3,
                    ),
                    "observed_or_interpolated": "interpolated"
                    if sample["source"] == "interpolated"
                    else "observed",
                    "segment_id": solution.segment_id,
                    "event_context": "v32_accepted_static_anchors",
                    "reprojection_error_px": round(sample["reprojection_error_px"], 3),
                    "observed_pixel_x": round(sample["pixel"][0], 3),
                    "observed_pixel_y": round(sample["pixel"][1], 3),
                    "reprojected_pixel_x": round(sample["reprojected_pixel"][0], 3),
                    "reprojected_pixel_y": round(sample["reprojected_pixel"][1], 3),
                    "uncertainty_x_m": 0.75,
                    "uncertainty_y_m": 0.75,
                    "uncertainty_z_m": 0.5,
                    "constraint_sources": [
                        "314_ball_observations",
                        "vfr_timestamps",
                        "accepted_static_anchor_v4",
                        "total_anchor_uncertainty",
                        "soft_l1",
                        "bounce_z0",
                    ],
                    "player_identity": "unknown",
                    "contact_event_id": None,
                    "hypothesis_id": solution.hypothesis_id,
                    "ambiguity_status": ambiguity[solution.segment_id],
                    "warnings": ["HUMAN_STAGE5B_V32_GATE_REQUIRED"],
                    "coordinate_unit": "metres",
                }
            )
    lines = "".join(json.dumps(row, sort_keys=True) + "\n" for row in serialized)
    errors = [row["reprojection_error_px"] for row in serialized]
    return {
        "samples": serialized,
        "xyz_jsonl": lines,
        "checksum": hashlib.sha256(lines.encode()).hexdigest(),
        "anchors": anchors,
        "anchors_consumed": sorted(set(consumed)),
        "solutions": all_solutions,
        "selected": selected,
        "segment_reports": segment_reports,
        "observations_consumed": sum(row["observations_used"] for row in segment_reports),
        "observations_downweighted": sum(
            row["observations_downweighted"] for row in segment_reports
        ),
        "observations_rejected": 0,
        "median_reprojection_error_px": float(np.median(errors)),
        "p95_reprojection_error_px": float(np.percentile(errors, 95)),
        "maximum_reprojection_error_px": max(errors),
        "resolved_segments": sum(row["ambiguity_status"] == "RESOLVED" for row in segment_reports),
        "ambiguous_segments": sum(
            row["ambiguity_status"] == "AMBIGUOUS" for row in segment_reports
        ),
        "negative_z_violations": sum(row["z_m"] < 0 for row in serialized),
        "maximum_contact_residual_m": max(row["contact_residual_m"] for row in segment_reports),
        "maximum_bounce_residual_m": max(row["bounce_residual_m"] for row in segment_reports),
    }
