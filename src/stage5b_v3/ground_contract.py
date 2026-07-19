"""Explicit Stage 5A.2 input contract for the next Stage 5B producer run."""

from __future__ import annotations

from typing import Any

import numpy as np


def contact_prior_from_ground(row: dict[str, Any], contact_height_m: float) -> np.ndarray:
    """Create the player-aware prior consumed by a future XYZ objective."""
    xy = row.get("fused_xy_m") or row["homography_xy_m"]
    return np.asarray([float(xy[0]), float(xy[1]), float(contact_height_m)], dtype=float)


def anchor_objective_residual(candidate_xyz: np.ndarray, ground_row: dict[str, Any]) -> np.ndarray:
    """Return a calibration-dependent player/contact prior residual."""
    prior = contact_prior_from_ground(ground_row, float(candidate_xyz[2]))
    uncertainty = max(0.05, float(ground_row["metric_uncertainty_m"]))
    return (np.asarray(candidate_xyz, dtype=float) - prior) / uncertainty


STAGE5A2_PRODUCER_INPUTS = (
    "extended_ground_homography.json",
    "extended_ground_camera.json",
    "player_ground_positions_v2.jsonl",
)
