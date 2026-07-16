"""Planar homography decomposition into assumption-based camera candidates."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from src.geometry.camera_model import CameraModel


def rotation_angles_degrees(R: np.ndarray) -> dict[str, float]:
    """Return a documented ZYX yaw/pitch/roll description (diagnostic only)."""
    pitch = math.atan2(-R[2, 0], math.hypot(R[0, 0], R[1, 0]))
    yaw = math.atan2(R[1, 0], R[0, 0])
    roll = math.atan2(R[2, 1], R[2, 2])
    return {"yaw": math.degrees(yaw), "pitch": math.degrees(pitch), "roll": math.degrees(roll)}


def decompose_planar_homography(
    H_court_to_pixel: Any,
    K: Any,
    image_width: int,
    image_height: int,
    *,
    orthonormal_tolerance: float = 1e-5,
) -> CameraModel:
    """Decompose ``H = K [r1 r2 t]`` choosing the positive-depth branch."""
    H = np.asarray(H_court_to_pixel, dtype=np.float64)
    intrinsics = np.asarray(K, dtype=np.float64)
    if H.shape != (3, 3) or not np.all(np.isfinite(H)) or abs(np.linalg.det(H)) < 1e-12:
        raise ValueError("H must be finite, non-singular 3x3")
    if intrinsics.shape != (3, 3):
        raise ValueError("K must have shape 3x3")
    A = np.linalg.solve(intrinsics, H)
    scale = 2.0 / (np.linalg.norm(A[:, 0]) + np.linalg.norm(A[:, 1]))
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("homography decomposition scale is invalid")
    raw = np.column_stack((A[:, 0] * scale, A[:, 1] * scale))
    U, _singular, Vt = np.linalg.svd(raw, full_matrices=False)
    ortho = U @ Vt
    r1, r2 = ortho[:, 0], ortho[:, 1]
    r3 = np.cross(r1, r2)
    R = np.column_stack((r1, r2, r3))
    t = A[:, 2] * scale
    if np.linalg.det(R) < 0:
        R = -R
        t = -t
    candidate = CameraModel(intrinsics, R, t, image_width, image_height)
    if not np.allclose(R.T @ R, np.eye(3), atol=orthonormal_tolerance):
        raise ValueError("decomposition did not produce an orthonormal rotation")
    return candidate


def intrinsic_matrix(focal: float, cx: float, cy: float) -> np.ndarray:
    if focal <= 0 or not np.all(np.isfinite([focal, cx, cy])):
        raise ValueError("focal and principal point must be finite; focal > 0")
    return np.array([[focal, 0.0, cx], [0.0, focal, cy], [0.0, 0.0, 1.0]], dtype=np.float64)
