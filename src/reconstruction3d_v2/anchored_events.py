"""Event points constrained to their camera rays."""

from __future__ import annotations

from typing import Any

import numpy as np

from src.geometry.camera_model import CameraModel


def point_on_ray_at_height(
    camera: CameraModel, pixel: tuple[float, float], height_m: float
) -> np.ndarray:
    origin, direction = camera.world_ray_from_pixel(*pixel)
    if abs(direction[2]) < 1e-12:
        raise ValueError("event ray is parallel to the requested height plane")
    distance = (float(height_m) - origin[2]) / direction[2]
    if distance <= 0:
        raise ValueError("event ray intersection is behind the camera")
    return origin + distance * direction


def bounce_on_ground(camera: CameraModel, pixel: tuple[float, float]) -> np.ndarray:
    point = camera.intersect_ray_with_ground(*pixel)
    point[2] = 0.0
    return point


def event_point(
    camera: CameraModel, event: dict[str, Any], pixel: tuple[float, float], height_m: float
) -> np.ndarray:
    if event["type"] == "bounce":
        return bounce_on_ground(camera, pixel)
    return point_on_ray_at_height(camera, pixel, height_m)


def side_pass(event: dict[str, Any], point: np.ndarray) -> tuple[bool, str]:
    side = str(event.get("side", "unknown"))
    if side == "near" and point[1] >= 0:
        return False, "near_event_has_nonnegative_Y"
    if side == "far" and point[1] <= 0:
        return False, "far_event_has_nonpositive_Y"
    return True, "side_constraint_pass"
