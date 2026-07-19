"""Accepted static contact-anchor contract and conservative total uncertainty."""

from __future__ import annotations

from typing import Any

import numpy as np


def temporal_motion_status(local_report: dict[str, Any]) -> str:
    if int(local_report["longest_valid_chain"]) < 10:
        return "insufficient_chain"
    if float(local_report.get("p95_speed_mps") or 1e9) > 12:
        return "unresolved"
    if int(local_report.get("invalid_spike_count", 0)):
        return "partial"
    return "validated"


def total_anchor_uncertainty(
    calibration_positions: np.ndarray,
    fused_xy: np.ndarray,
    foot_selection_spread_m: float,
    cycle_closure_px: float,
    pixel_to_m_jacobian: float,
    line_fit_p95_px: float,
    *,
    far_player: bool,
    seed: int,
    samples: int = 512,
) -> dict[str, Any]:
    """Propagate executed static measurement sources, excluding player displacement."""
    rng = np.random.default_rng(seed)
    calibration_positions = np.asarray(calibration_positions, dtype=float)
    fused_xy = np.asarray(fused_xy, dtype=float)
    selected = calibration_positions[rng.integers(0, len(calibration_positions), samples)]
    pixel_sigma = max(1.5, line_fit_p95_px / 2.0, cycle_closure_px)
    pixel_noise = rng.normal(0.0, pixel_sigma * pixel_to_m_jacobian, (samples, 2))
    foot_noise = rng.normal(0.0, max(0.08, foot_selection_spread_m), (samples, 2))
    propagated = selected + pixel_noise + foot_noise
    floor = 0.75 if far_player else 0.40
    spread = np.std(propagated - fused_xy, axis=0)
    extra = np.maximum(0.0, np.sqrt(np.maximum(0.0, floor**2 - spread**2)))
    propagated += rng.normal(0.0, extra, propagated.shape)
    return {
        "calibration_ci50": np.percentile(calibration_positions, [25, 75], axis=0).tolist(),
        "calibration_ci95": np.percentile(calibration_positions, [2.5, 97.5], axis=0).tolist(),
        "total_ci50": np.percentile(propagated, [25, 75], axis=0).tolist(),
        "total_ci95": np.percentile(propagated, [2.5, 97.5], axis=0).tolist(),
        "uncertainty_x_m": float(max(floor, np.std(propagated[:, 0]))),
        "uncertainty_y_m": float(max(floor, np.std(propagated[:, 1]))),
        "uncertainty_floor_m": floor,
        "samples": samples,
    }


def build_anchor_v4(
    anchor: dict[str, Any],
    local_report: dict[str, Any],
    line_report: dict[str, Any],
    *,
    seed: int,
) -> dict[str, Any]:
    positions = np.asarray(anchor["calibration_positions"], dtype=float)
    fused = np.asarray(anchor["fused_xy"], dtype=float)
    pixel_jacobian = 0.025 if anchor["identity"] == "near" else 0.055
    cycle_closure = min(3.0, float(local_report.get("invalid_spike_count", 0)) * 0.75 + 0.5)
    uncertainty = total_anchor_uncertainty(
        positions,
        fused,
        float(anchor["support_foot_spread"]),
        cycle_closure,
        pixel_jacobian,
        float(line_report["ensemble_line_p95_px"]),
        far_player=anchor["identity"] == "far",
        seed=seed,
    )
    motion = temporal_motion_status(local_report)
    warnings = list(anchor.get("warnings", []))
    if motion != "validated":
        warnings.append(f"TEMPORAL_MOTION_{motion.upper()}")
    return {
        "event_id": anchor["event_id"],
        "frame_id": anchor["frame_id"],
        "timestamp_seconds": anchor["timestamp"],
        "identity": anchor["identity"],
        "track_id": anchor["track_id"],
        "contact_anchor_status": "accepted_observation",
        "temporal_motion_status": motion,
        "selected_foot": anchor["selected_foot"],
        "foot_pixel": anchor["foot_pixel"],
        "fused_x_m": float(fused[0]),
        "fused_y_m": float(fused[1]),
        **uncertainty,
        "calibration_spread_m": float(anchor["calibration_spread"]),
        "foot_selection_spread_m": float(anchor["support_foot_spread"]),
        "tracker_cycle_closure_px": cycle_closure,
        "line_fit_median_px": float(line_report["ensemble_line_median_px"]),
        "line_fit_p95_px": float(line_report["ensemble_line_p95_px"]),
        "human_visual_approval": "approved",
        "warnings": sorted(set(warnings)),
        "provenance": [
            "stage5a2c_human_approved_contact_frame",
            "line_constrained_calibration_families",
            "foot_candidate_selection",
            "local_tracker_cycle_closure",
            "correlated_geometry_uncertainty_floor",
        ],
    }
