"""Stage 5B v3.1 coordinate-audited, observation-optimized reconstruction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from src.geometry.camera_model import CameraModel

from .coordinate_audit import audit_coordinates
from .optimization import optimize_segment
from .reconstruction import _load_ball, reconstruct


def reconstruct_v31(
    camera_path: Path,
    homography_path: Path,
    ball_track_path: Path,
    events_path: Path,
    p1_results_path: Path,
    config_path: Path,
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
    observations = _load_ball(ball_track_path)
    best_baseline = min(
        baseline["hypotheses"], key=lambda item: item["median_reprojection_error_px"]
    )
    anchors = best_baseline["anchors"]
    rng = np.random.default_rng(seed)
    solutions = []
    selected = []
    for index, (start, end) in enumerate(zip(anchors, anchors[1:], strict=False), 1):
        segment_id = f"flight_{index:02d}"
        rows = [
            row
            for row in observations
            if start["timestamp_seconds"] <= row["timestamp_seconds"]
            and (
                row["timestamp_seconds"] < end["timestamp_seconds"]
                or index == len(anchors) - 1
            )
        ]
        candidates = optimize_segment(
            camera, segment_id, rows, start, end, config, rng, starts_per_segment
        )
        solutions.extend(candidates)
        selected.append(candidates[0])
    errors = [sample["reprojection_error_px"] for solution in selected for sample in solution.samples]
    serialized = []
    for solution in selected:
        alternatives = [item for item in solutions if item.segment_id == solution.segment_id]
        ambiguous = any(
            item.cost <= solution.cost * float(config["ambiguity_cost_ratio"])
            and abs(item.parameters[2] - solution.parameters[2])
            > float(config["ambiguity_depth_threshold_m"])
            for item in alternatives[1:]
        )
        for sample in solution.samples:
            point = sample["xyz"]
            row = {
                "frame_id": sample["frame_id"],
                "timestamp_seconds": round(sample["timestamp_seconds"], 6),
                "x_m": round(point[0], 3),
                "y_m": round(point[1], 3),
                "z_m": round(max(0.0, point[2]), 3),
                "confidence": round(float(sample["confidence"]) * np.exp(-sample["reprojection_error_px"] / 24.0), 3),
                "observed_or_interpolated": "interpolated" if sample["source"] == "interpolated" else "observed",
                "segment_id": solution.segment_id,
                "event_context": "optimized_flight",
                "reprojection_error_px": round(sample["reprojection_error_px"], 3),
                "observed_pixel_x": round(sample["pixel"][0], 3),
                "observed_pixel_y": round(sample["pixel"][1], 3),
                "reprojected_pixel_x": round(sample["reprojected_pixel"][0], 3),
                "reprojected_pixel_y": round(sample["reprojected_pixel"][1], 3),
                "uncertainty_x_m": 0.35,
                "uncertainty_y_m": 0.35,
                "uncertainty_z_m": 0.5 if ambiguous else 0.3,
                "constraint_sources": ["all_segment_ball_observations", "vfr_timestamps", "soft_l1", "player_contact_anchor", "bounce_z0", "homography_coordinate_audit"],
                "player_identity": "unknown",
                "contact_event_id": None,
                "hypothesis_id": solution.hypothesis_id,
                "ambiguity_status": "AMBIGUOUS" if ambiguous else "RESOLVED",
                "warnings": ["HUMAN_GATE_REQUIRED"],
                "coordinate_unit": "metres",
            }
            serialized.append(row)
    lines = "".join(json.dumps(row, sort_keys=True) + "\n" for row in serialized)
    baseline_errors = [row["reprojection_error_px"] for row in baseline["samples"]]
    coordinate_audit = audit_coordinates(homography_path, p1_results_path)
    return {
        "samples": serialized,
        "xyz_jsonl": lines,
        "checksum": hashlib.sha256(lines.encode()).hexdigest(),
        "coordinate_audit": coordinate_audit,
        "baseline_median_error_px": float(np.median(baseline_errors)),
        "baseline_p95_error_px": float(np.percentile(baseline_errors, 95)),
        "optimized_median_error_px": float(np.median(errors)),
        "optimized_p95_error_px": float(np.percentile(errors, 95)),
        "observations_in_objective": sum(item.observations_in_objective for item in selected),
        "solutions": solutions,
        "selected": selected,
        "contacts": baseline["contacts"],
        "segments_reconstructed": len(selected),
    }
