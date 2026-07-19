"""Camera helpers for intersecting monocular rays with candidate height planes."""

from __future__ import annotations

import numpy as np

from src.geometry.camera_model import CameraModel


def point_on_pixel_ray_at_height(camera: CameraModel, pixel: tuple[float, float], z_m: float) -> np.ndarray:
    origin, direction = camera.world_ray_from_pixel(*pixel)
    if abs(direction[2]) < 1e-12:
        raise ValueError("pixel ray is parallel to height plane")
    distance = (float(z_m) - origin[2]) / direction[2]
    if distance <= 0:
        raise ValueError("height-plane intersection is behind camera")
    return origin + distance * direction
