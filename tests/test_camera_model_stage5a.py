"""Numerical contracts for the Stage 5A geometry primitives."""

import json
from pathlib import Path

import numpy as np
import pytest

from src.geometry.camera_calibration import decompose_planar_homography, intrinsic_matrix
from src.geometry.camera_model import CameraModel


def _camera() -> CameraModel:
    return CameraModel(
        intrinsic_matrix(800.0, 320.0, 240.0),
        np.diag([1.0, -1.0, -1.0]),
        np.array([0.0, 0.0, 5.0]),
        640,
        480,
    )


def test_coordinate_convention_is_right_handed_and_ground_intersection() -> None:
    model = _camera()
    assert model.coordinate_system.right_handed
    assert model.coordinate_system.y_zero == "net plane"
    assert np.allclose(model.camera_center_world, [0, 0, 5])


def test_projection_and_ray_round_trip() -> None:
    # Camera looks along +Z in this synthetic frame; put it above the ground by using R flip.
    R = np.diag([1.0, -1.0, -1.0])
    model = CameraModel(intrinsic_matrix(800, 320, 240), R, np.array([0.0, 0.0, 5.0]), 640, 480)
    pixel = model.project_world_to_pixel([[0.0, 0.0, 0.0]])[0]
    assert np.allclose(pixel, [320, 240])
    ground = model.intersect_ray_with_ground(*pixel)
    assert np.allclose(ground, [0, 0, 0])


def test_camera_center_and_projection_matrix() -> None:
    model = _camera()
    assert model.projection_matrix.shape == (3, 4)
    assert np.allclose(model.camera_center_world, [0.0, 0.0, 5.0])


def test_invalid_rotation_and_ground_camera_rejected() -> None:
    with pytest.raises(ValueError, match="orthonormal"):
        CameraModel(intrinsic_matrix(800, 320, 240), np.eye(3) * 2, [0, 0, 5], 640, 480)
    with pytest.raises(ValueError, match="above"):
        CameraModel(intrinsic_matrix(800, 320, 240), np.eye(3), [0, 0, 5], 640, 480)


def test_serialization_round_trip(tmp_path: Path) -> None:
    model = _camera()
    path = tmp_path / "camera.json"
    model.write_json(path, status="NEEDS_VERTICAL_REFERENCE")
    loaded = CameraModel.read_json(path)
    assert np.allclose(loaded.K, model.K)
    assert np.allclose(loaded.R, model.R)
    assert loaded.image_width == 640


def test_synthetic_homography_decomposition() -> None:
    # A planar camera with Z=0 and a valid right-handed pose.
    R = np.diag([1.0, -1.0, -1.0])
    K = intrinsic_matrix(900, 320, 240)
    t = np.array([0.0, 0.0, 8.0])
    H = K @ np.column_stack((R[:, 0], R[:, 1], t))
    model = decompose_planar_homography(H, K, 640, 480)
    assert np.isclose(np.linalg.det(model.R), 1.0)
    assert np.all(model.camera_coordinates([[-1, -1, 0], [1, 1, 0]])[:, 2] > 0)


def test_a2_homography_inverse_and_error() -> None:
    payload = json.loads(Path("data/clips/nivel_a2_01/homography.json").read_text())
    H = np.asarray(payload["H_pixel_to_court"])
    Hi = np.asarray(payload["H_court_to_pixel"])
    product = H @ Hi
    product /= product[2, 2]
    assert np.max(np.abs(product - np.eye(3))) < 1e-10
    assert payload["reprojection_error_pixels_mean"] < 5.0
