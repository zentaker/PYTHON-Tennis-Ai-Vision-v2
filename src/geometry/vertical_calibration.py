"""Refine a pinhole camera with a small set of non-coplanar references."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from scipy.optimize import least_squares

from src.geometry.camera_model import CameraModel


def _rotation_vector(rotation: np.ndarray) -> np.ndarray:
    vector, _ = cv2.Rodrigues(np.asarray(rotation, dtype=np.float64))
    return vector[:, 0]


def refine_pinhole_camera(
    initial: CameraModel,
    world_points: Any,
    pixel_points: Any,
    *,
    max_nfev: int = 1200,
) -> tuple[CameraModel, dict[str, float]]:
    """Refine ``K,R,t`` from coplanar plus vertical correspondences.

    The optimizer is deliberately small and deterministic. It is a backend primitive;
    it does not decide readiness or overwrite the approved planar homography.
    """
    world = np.asarray(world_points, dtype=np.float64)
    pixels = np.asarray(pixel_points, dtype=np.float64)
    if world.ndim != 2 or world.shape[1] != 3 or pixels.shape != (len(world), 2):
        raise ValueError("world_points must be Nx3 and pixel_points Nx2")
    if len(world) < 6 or not np.all(np.isfinite(world)) or not np.all(np.isfinite(pixels)):
        raise ValueError("at least six finite correspondences are required")
    initial_params = np.array(
        [
            np.log(initial.K[0, 0]),
            np.log(initial.K[1, 1]),
            initial.K[0, 2],
            initial.K[1, 2],
            *_rotation_vector(initial.R),
            *initial.t,
        ],
        dtype=np.float64,
    )

    def unpack(params: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        K = np.array(
            [[np.exp(params[0]), 0.0, params[2]], [0.0, np.exp(params[1]), params[3]], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )
        R, _ = cv2.Rodrigues(params[4:7])
        return K, R, params[7:10]

    def residual(params: np.ndarray) -> np.ndarray:
        K, R, t = unpack(params)
        camera = (R @ world.T + t[:, None]).T
        if np.any(camera[:, 2] <= 1e-6):
            return np.full(len(world) * 2, 1e5, dtype=np.float64)
        projected = (K @ camera.T).T
        projected = projected[:, :2] / projected[:, 2:3]
        return (projected - pixels).reshape(-1)

    result = least_squares(residual, initial_params, max_nfev=max_nfev, method="trf")
    K, R, t = unpack(result.x)
    model = CameraModel(K, R, t, initial.image_width, initial.image_height, initial.coordinate_system)
    errors = model.reprojection_error(world, pixels)
    return model, {
        "optimizer_cost": float(result.cost),
        "optimizer_optimality": float(result.optimality),
        "reprojection_mean_px": float(errors.mean()),
        "reprojection_max_px": float(errors.max()),
        "iterations": float(result.nfev),
    }
