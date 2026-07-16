"""Reprojection and geometry diagnostics shared by Stage 5A."""

from __future__ import annotations

from typing import Any

import numpy as np


def project_homography(H: Any, points_xy: Any) -> np.ndarray:
    matrix = np.asarray(H, dtype=np.float64)
    points = np.asarray(points_xy, dtype=np.float64)
    if matrix.shape != (3, 3) or points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("H must be 3x3 and points Nx2")
    homogeneous = np.column_stack((points, np.ones(len(points))))
    projected = (matrix @ homogeneous.T).T
    if np.any(np.abs(projected[:, 2]) < 1e-12):
        raise ValueError("homography projects a point to infinity")
    return projected[:, :2] / projected[:, 2:3]


def summarize_errors(errors: Any) -> dict[str, float]:
    values = np.asarray(errors, dtype=np.float64)
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("errors must contain finite values")
    return {"mean": float(values.mean()), "median": float(np.median(values)), "max": float(values.max()), "rmse": float(np.sqrt(np.mean(values**2)))}


def vertical_sensitivity(models: list[Any], points_xy: tuple[float, float], heights: list[float]) -> dict[str, Any]:
    projections = []
    for model in models:
        rows = []
        for height in heights:
            rows.append(model.project_world_to_pixel([[points_xy[0], points_xy[1], height]])[0].tolist())
        projections.append(rows)
    spread = np.ptp(np.asarray(projections, dtype=np.float64), axis=0)
    return {"point_world_xy": list(points_xy), "heights_m": heights, "model_projections": projections, "spread_pixels": spread.tolist(), "max_spread_pixels": float(spread.max())}
