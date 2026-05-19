from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.court.coordinates import calibration_court_points
from src.court.homography import (
    apply_homography,
    compute_and_write_homography,
    compute_homography,
    reprojection_errors_pixels,
)


def test_compute_homography_maps_corner_within_one_centimeter() -> None:
    corners_court = dict(calibration_court_points("doubles"))
    corners_pixel = {
        name: (x * 100.0 + 960.0, -y * 20.0 + 540.0)
        for name, (x, y) in corners_court.items()
    }

    homography = compute_homography(corners_pixel, corners_court)
    projected = apply_homography(homography, np.array([corners_pixel["far_left"]]))[0]

    assert projected == pytest.approx(corners_court["far_left"], abs=0.01)


def test_reprojection_errors_pixels_are_near_zero_for_exact_points() -> None:
    corners_court = dict(calibration_court_points("doubles"))
    corners_pixel = {
        name: (x * 50.0 + 1000.0, y * -40.0 + 600.0)
        for name, (x, y) in corners_court.items()
    }
    homography = compute_homography(corners_pixel, corners_court)

    errors = reprojection_errors_pixels(homography, corners_pixel, corners_court)

    assert float(errors.max()) < 1e-4


def test_compute_and_write_homography_persists_expected_schema(tmp_path: Path) -> None:
    corners_court = dict(calibration_court_points("doubles"))
    clicked = {
        "layout": "doubles",
        "court_corners_pixel": {
            name: [x * 60.0 + 800.0, y * -30.0 + 500.0]
            for name, (x, y) in corners_court.items()
        },
    }
    corners_path = tmp_path / "corners.json"
    output_path = tmp_path / "homography.json"
    corners_path.write_text(json.dumps(clicked), encoding="utf-8")

    payload = compute_and_write_homography(corners_path, output_path)

    assert output_path.exists()
    assert payload["court_mode"] == "doubles"
    assert payload["method"] == "cv2.findHomography(method=0)"
    assert payload["reprojection_error_pixels_mean"] < 1e-4
