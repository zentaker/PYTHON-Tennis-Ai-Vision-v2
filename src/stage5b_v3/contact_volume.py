"""Player-aware feasible ball-contact volumes; ground anchors are never ball contacts."""

from __future__ import annotations

from typing import Any

import numpy as np


def keypoint(pose: dict[str, Any], name: str) -> dict[str, Any] | None:
    return next((row for row in pose["keypoints"] if row["name"] == name), None)


def build_contact_volume(
    anchor: dict[str, Any],
    pose: dict[str, Any],
    ball_pixel: tuple[float, float],
    *,
    racket_extension_m: float = 0.75,
    body_reach_m: float = 0.75,
    height_range_m: tuple[float, float] = (0.35, 3.40),
) -> dict[str, Any]:
    """Build one uncertainty-expanded, event-independent feasible volume."""
    wrists = [keypoint(pose, "left_wrist"), keypoint(pose, "right_wrist")]
    wrists = [row for row in wrists if row is not None and row["visible"]]
    shoulders = [keypoint(pose, "left_shoulder"), keypoint(pose, "right_shoulder")]
    hips = [keypoint(pose, "left_hip"), keypoint(pose, "right_hip")]
    reach = body_reach_m + racket_extension_m
    ci95 = np.asarray(anchor["total_ci95"], dtype=float)
    lower = [float(ci95[0, 0] - reach), float(ci95[0, 1] - reach), height_range_m[0]]
    upper = [float(ci95[1, 0] + reach), float(ci95[1, 1] + reach), height_range_m[1]]
    wrist_candidates = [
        {
            "pixel": [row["x"], row["y"]],
            "confidence": row["confidence"],
            "ray_status": "camera_ray_candidate",
        }
        for row in wrists
    ]
    return {
        "event_id": anchor["event_id"],
        "identity": anchor["identity"],
        "player_ground_anchor": [anchor["fused_x_m"], anchor["fused_y_m"], 0.0],
        "anchor_total_ci95": anchor["total_ci95"],
        "ball_pixel": list(ball_pixel),
        "wrist_ray_candidates": wrist_candidates,
        "shoulder_pixels": [[row["x"], row["y"]] for row in shoulders if row],
        "hip_pixels": [[row["x"], row["y"]] for row in hips if row],
        "racket_contact_candidates": [row["pixel"] for row in wrist_candidates],
        "racket_extension_m": racket_extension_m,
        "body_reach_m": body_reach_m,
        "feasible_horizontal_reach_m": reach,
        "feasible_vertical_range_m": list(height_range_m),
        "feasible_3d_contact_volume": {"lower_xyz": lower, "upper_xyz": upper},
        "uncertainty_expanded_volume": True,
        "warnings": [] if len(wrist_candidates) == 2 else ["LIMITED_WRIST_SUPPORT"],
    }


def contact_volume_metrics(point_xyz: list[float], volume: dict[str, Any]) -> dict[str, float]:
    point = np.asarray(point_xyz, dtype=float)
    ground = np.asarray(volume["player_ground_anchor"], dtype=float)
    bounds = volume["feasible_3d_contact_volume"]
    lower, upper = np.asarray(bounds["lower_xyz"]), np.asarray(bounds["upper_xyz"])
    outside = np.maximum(lower - point, 0) + np.maximum(point - upper, 0)
    scale = np.maximum((upper - lower) / 2, 1e-6)
    return {
        "player_ground_distance_m": float(np.linalg.norm(point - ground)),
        "contact_volume_excess_m": float(np.linalg.norm(outside)),
        "normalized_residual": float(np.linalg.norm(outside / scale)),
    }


def normalized_contact_residual(point_xyz: list[float], volume: dict[str, Any]) -> np.ndarray:
    bounds = volume["feasible_3d_contact_volume"]
    point = np.asarray(point_xyz, dtype=float)
    lower, upper = np.asarray(bounds["lower_xyz"]), np.asarray(bounds["upper_xyz"])
    sigma = np.maximum((upper - lower) / 2, 0.25)
    return (np.maximum(lower - point, 0) + np.maximum(point - upper, 0)) / sigma
