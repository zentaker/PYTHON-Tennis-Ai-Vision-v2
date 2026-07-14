from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.court.coordinates import calibration_court_points
from src.court.homography import (
    apply_homography,
    compute_and_write_homography,
    compute_homography,
    orientation_validation,
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


def test_a2_homography_uses_explicit_multiclip_paths_and_canonical_dimensions(
    tmp_path: Path,
) -> None:
    corners_court = dict(calibration_court_points("doubles"))
    a2_directory = tmp_path / "data" / "clips" / "nivel_a2_01"
    a2_directory.mkdir(parents=True)
    frame_path = a2_directory / "reference_frame.png"
    assert cv2.imwrite(str(frame_path), np.zeros((1536, 2746, 3), dtype=np.uint8))
    clicked = {
        "image_path": str(frame_path),
        "layout": "doubles",
        "method": "manual_web_click",
        "court_corners_pixel": {
            name: [x * 100.0 + 1373.0, -y * 40.0 + 768.0]
            for name, (x, y) in corners_court.items()
        },
    }
    corners_path = a2_directory / "court_corners_pixel.json"
    output_path = a2_directory / "homography.json"
    corners_path.write_text(json.dumps(clicked), encoding="utf-8")

    payload = compute_and_write_homography(
        corners_path,
        output_path,
        frame_path=frame_path,
        clip_id="nivel_a2_01",
    )

    assert output_path.exists()
    assert "reference_clip" not in str(output_path)
    assert payload["clip_id"] == "nivel_a2_01"
    assert payload["frame_dimensions"] == {"width": 2746, "height": 1536}
    assert payload["orientation_validation"]["passed"] is True  # type: ignore[index]
    assert np.array(payload["H_court_to_pixel"]).shape == (3, 3)


def test_orientation_validation_rejects_lateral_frame() -> None:
    result = orientation_validation(
        {
            "far_left": (200.0, 200.0),
            "far_right": (800.0, 200.0),
            "near_left": (100.0, 1200.0),
            "near_right": (900.0, 1200.0),
            "far_left_service": (300.0, 400.0),
            "far_right_service": (700.0, 400.0),
            "near_left_service": (250.0, 900.0),
            "near_right_service": (750.0, 900.0),
        },
        frame_width=1536,
        frame_height=2746,
    )

    assert result["canonical_horizontal"] is False
    assert result["passed"] is False
