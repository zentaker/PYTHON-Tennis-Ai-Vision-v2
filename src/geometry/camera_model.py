"""Float64 pinhole camera model in the project's explicit court frame."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class CoordinateSystem:
    """Right-handed court frame: X right, Y toward the far baseline, Z up."""

    name: str = "court_center_right_handed"
    origin: str = "geometric center of court (net midpoint)"
    x_axis: str = "court width; positive from left sideline toward right sideline"
    y_axis: str = "court length; positive from net toward far baseline"
    z_axis: str = "height; positive upward from the court plane"
    units: str = "metres"
    right_handed: bool = True
    z_zero: str = "court plane"
    y_zero: str = "net plane"

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _array(value: Any, shape: tuple[int, ...], name: str) -> np.ndarray:
    result = np.asarray(value, dtype=np.float64)
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be finite with shape {shape}")
    return result


@dataclass
class CameraModel:
    """Pinhole model ``p ~ K [R|t] P`` with world-to-camera extrinsics."""

    K: np.ndarray
    R: np.ndarray
    t: np.ndarray
    image_width: int
    image_height: int
    coordinate_system: CoordinateSystem = CoordinateSystem()

    def __post_init__(self) -> None:
        self.K = _array(self.K, (3, 3), "K")
        self.R = _array(self.R, (3, 3), "R")
        self.t = _array(self.t, (3,), "t")
        if self.K[2, 2] == 0 or self.K[0, 0] <= 0 or self.K[1, 1] <= 0:
            raise ValueError("focal lengths and K[2,2] must be positive")
        if not np.allclose(self.K[2], [0, 0, self.K[2, 2]], atol=1e-9):
            raise ValueError("K must have a pinhole final row")
        if not np.allclose(self.R.T @ self.R, np.eye(3), atol=1e-6):
            raise ValueError("R is not orthonormal")
        if not np.isclose(np.linalg.det(self.R), 1.0, atol=1e-6):
            raise ValueError("det(R) must be approximately +1")
        if self.image_width <= 0 or self.image_height <= 0:
            raise ValueError("image dimensions must be positive")
        if self.camera_center_world[2] <= 0:
            raise ValueError("camera must be above the court plane")

    @property
    def camera_center_world(self) -> np.ndarray:
        return -self.R.T @ self.t

    @property
    def projection_matrix(self) -> np.ndarray:
        return self.K @ np.column_stack((self.R, self.t))

    @property
    def height_m(self) -> float:
        return float(self.camera_center_world[2])

    def camera_coordinates(self, points_world: Any) -> np.ndarray:
        points = np.asarray(points_world, dtype=np.float64)
        if points.ndim == 1:
            points = points.reshape(1, 3)
        if points.ndim != 2 or points.shape[1] != 3 or not np.all(np.isfinite(points)):
            raise ValueError("points_world must have shape Nx3 and be finite")
        return (self.R @ points.T + self.t[:, None]).T

    def project_world_to_pixel(self, points_world: Any, *, require_positive_depth: bool = True) -> np.ndarray:
        camera = self.camera_coordinates(points_world)
        if require_positive_depth and np.any(camera[:, 2] <= 0):
            raise ValueError("point has non-positive camera depth")
        pixels = (self.K @ camera.T).T
        return pixels[:, :2] / pixels[:, 2:3]

    def world_ray_from_pixel(self, u: float, v: float) -> tuple[np.ndarray, np.ndarray]:
        pixel = np.array([float(u), float(v), 1.0], dtype=np.float64)
        direction_camera = np.linalg.solve(self.K, pixel)
        direction_world = self.R.T @ direction_camera
        direction_world /= np.linalg.norm(direction_world)
        return self.camera_center_world.copy(), direction_world

    def intersect_ray_with_ground(self, u: float, v: float) -> np.ndarray:
        origin, direction = self.world_ray_from_pixel(u, v)
        if abs(direction[2]) < 1e-12:
            raise ValueError("ray is parallel to the court plane")
        distance = -origin[2] / direction[2]
        if distance <= 0:
            raise ValueError("ground intersection is behind the camera")
        return origin + distance * direction

    def reprojection_error(self, points_world: Any, pixels_expected: Any) -> np.ndarray:
        expected = _array(pixels_expected, (len(np.asarray(pixels_expected)), 2), "pixels_expected")
        projected = self.project_world_to_pixel(points_world)
        if projected.shape != expected.shape:
            raise ValueError("world and pixel point counts differ")
        return np.linalg.norm(projected - expected, axis=1)

    def to_dict(self, **metadata: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "coordinate_system": self.coordinate_system.to_dict(),
            "K": self.K.tolist(),
            "R": self.R.tolist(),
            "t": self.t.tolist(),
            "projection_matrix": self.projection_matrix.tolist(),
            "camera_center_world": self.camera_center_world.tolist(),
            "height_m": self.height_m,
            "image_dimensions": {"width": self.image_width, "height": self.image_height},
        }
        payload.update(metadata)
        return payload

    def write_json(self, path: Path, **metadata: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(**metadata), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CameraModel":
        dimensions = payload["image_dimensions"]
        cs_payload = payload.get("coordinate_system", {})
        cs = CoordinateSystem(**{k: cs_payload[k] for k in CoordinateSystem().__dict__ if k in cs_payload})
        return cls(payload["K"], payload["R"], payload["t"], int(dimensions["width"]), int(dimensions["height"]), cs)

    @classmethod
    def read_json(cls, path: Path) -> "CameraModel":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
