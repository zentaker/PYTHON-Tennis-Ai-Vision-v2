"""Robust observation-driven optimization for Stage 5B v3.1 flights."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import least_squares

from src.geometry.camera_model import CameraModel
from src.reconstruction3d_v2.ballistic_segments import endpoint_velocity


@dataclass(frozen=True, slots=True)
class SegmentSolution:
    segment_id: str
    hypothesis_id: str
    parameters: tuple[float, ...]
    cost: float
    median_error_px: float
    p95_error_px: float
    bounce_residual_m: float
    samples: tuple[dict[str, Any], ...]
    observations_in_objective: int
    optimizer_nfev: int


def _positions(parameters: np.ndarray, times: np.ndarray, gravity: float) -> np.ndarray:
    start, velocity = parameters[:3], parameters[3:]
    acceleration = np.array([0.0, 0.0, -gravity])
    return start + times[:, None] * velocity + 0.5 * times[:, None] ** 2 * acceleration


def optimize_segment(
    camera: CameraModel,
    segment_id: str,
    observations: list[dict[str, Any]],
    start_anchor: dict[str, Any],
    end_anchor: dict[str, Any],
    config: dict[str, Any],
    rng: np.random.Generator,
    starts: int = 3,
) -> tuple[SegmentSolution, ...]:
    t0 = float(start_anchor["timestamp_seconds"])
    times = np.array([row["timestamp_seconds"] - t0 for row in observations])
    duration = float(end_anchor["timestamp_seconds"] - t0)
    start_xyz = np.array([start_anchor["x_m"], start_anchor["y_m"], start_anchor["z_m"]])
    end_xyz = np.array([end_anchor["x_m"], end_anchor["y_m"], end_anchor["z_m"]])
    gravity = float(config["gravity_mps2"])
    initial = np.concatenate([start_xyz, endpoint_velocity(start_xyz, end_xyz, duration)])
    expected = np.array([row["pixel"] for row in observations])
    weights = np.sqrt(np.array([max(0.05, row["confidence"]) for row in observations]))
    pixel_sigma = float(config["ball_pixel_uncertainty_px"])
    anchor_sigma = float(config.get("anchor_uncertainty_m", 0.75))

    def anchor_scale(anchor: dict[str, Any]) -> np.ndarray:
        total = anchor.get("total_uncertainty_m")
        return np.asarray(total, dtype=float) if total is not None else np.full(3, anchor_sigma)

    def residual(parameters: np.ndarray) -> np.ndarray:
        xyz = _positions(parameters, times, gravity)
        try:
            projected = camera.project_world_to_pixel(xyz)
            reprojection = ((projected - expected) * weights[:, None] / pixel_sigma).ravel()
        except ValueError:
            reprojection = np.full(expected.size, 1e3)
        endpoint = _positions(parameters, np.array([duration]), gravity)[0]
        anchors = np.concatenate([
            (parameters[:3] - start_xyz) / anchor_scale(start_anchor),
            (endpoint - end_xyz) / anchor_scale(end_anchor),
        ])
        bounce = []
        bounce_tolerance = float(config.get("bounce_tolerance_m", 0.03))
        if float(start_anchor["z_m"]) == 0:
            bounce.append(parameters[2] / bounce_tolerance)
        if float(end_anchor["z_m"]) == 0:
            bounce.append(endpoint[2] / bounce_tolerance)
        negative = np.minimum(0.0, xyz[:, 2]) * float(config.get("negative_z_weight", 20.0))
        return np.concatenate([reprojection, anchors, bounce, negative])

    solutions = []
    for index in range(starts):
        trial = initial.copy()
        if index:
            trial += rng.normal(0.0, [0.3, 0.5, 0.25, 0.8, 1.2, 0.8])
        fit = least_squares(
            residual,
            trial,
            loss=str(config["robust_loss"]),
            f_scale=1.0,
            max_nfev=int(config.get("optimizer_max_nfev", 400)),
        )
        xyz = _positions(fit.x, times, gravity)
        projected = camera.project_world_to_pixel(xyz)
        errors = np.linalg.norm(projected - expected, axis=1)
        endpoint = _positions(fit.x, np.array([duration]), gravity)[0]
        bounce_residuals = []
        if float(start_anchor["z_m"]) == 0:
            bounce_residuals.append(abs(float(fit.x[2])))
        if float(end_anchor["z_m"]) == 0:
            bounce_residuals.append(abs(float(endpoint[2])))
        samples = tuple(
            {
                **row,
                "xyz": point.tolist(),
                "reprojected_pixel": pixel.tolist(),
                "reprojection_error_px": float(error),
            }
            for row, point, pixel, error in zip(observations, xyz, projected, errors, strict=True)
        )
        solutions.append(
            SegmentSolution(
                segment_id,
                f"{segment_id}_h{index:02d}",
                tuple(float(value) for value in fit.x),
                float(fit.cost),
                float(np.median(errors)),
                float(np.percentile(errors, 95)),
                max(bounce_residuals, default=0.0),
                samples,
                len(observations),
                int(fit.nfev),
            )
        )
    return tuple(sorted(solutions, key=lambda item: (item.cost, item.hypothesis_id)))
