from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.court.calibrate_web import (
    calibration_payload,
    image_size,
    render_html,
    sanitize_points,
    validate_calibration_points,
    write_calibration_json,
)
from src.court.coordinates import CALIBRATION_POINT_ORDER


VALID_POINTS = {
    "far_left": (600, 280),
    "far_right": (1300, 280),
    "near_left": (380, 770),
    "near_right": (1540, 770),
    "far_left_service": (690, 355),
    "far_right_service": (1230, 355),
    "near_left_service": (520, 605),
    "near_right_service": (1390, 605),
}


def raw_points(points: dict[str, tuple[int, int]]) -> list[dict[str, object]]:
    return [{"name": name, "x": points[name][0], "y": points[name][1]} for name in CALIBRATION_POINT_ORDER]


def test_sanitize_points_preserves_expected_order() -> None:
    assert sanitize_points(raw_points(VALID_POINTS)) == VALID_POINTS


def test_sanitize_points_rejects_wrong_order() -> None:
    points = raw_points(VALID_POINTS)
    points[0]["name"] = "near_left"

    with pytest.raises(ValueError, match="far_left"):
        sanitize_points(points)


def test_validate_calibration_points_accepts_plausible_points() -> None:
    assert validate_calibration_points(VALID_POINTS, 1920, 1080) == []


def test_validate_calibration_points_rejects_out_of_bounds() -> None:
    points = dict(VALID_POINTS)
    points["far_left"] = (-1, 280)

    errors = validate_calibration_points(points, 1920, 1080)

    assert any("fuera de bounds" in error for error in errors)


def test_validate_calibration_points_rejects_far_below_near() -> None:
    points = dict(VALID_POINTS)
    points["far_left"] = (600, 900)

    errors = validate_calibration_points(points, 1920, 1080)

    assert any("far_left" in error and "near_left" in error for error in errors)


def test_validate_calibration_points_rejects_service_outside_doubles() -> None:
    points = dict(VALID_POINTS)
    points["far_left_service"] = (100, 355)

    errors = validate_calibration_points(points, 1920, 1080)

    assert any("far_left_service" in error and "doubles" in error for error in errors)


def test_write_calibration_json_records_manual_web_method(tmp_path: Path) -> None:
    output_path = tmp_path / "court_corners_pixel.json"

    write_calibration_json(
        output_path,
        VALID_POINTS,
        Path("data/reference_clip/reference_frame.png"),
        "doubles",
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["method"] == "manual_web_click"
    assert payload["layout"] == "doubles"
    assert payload["court_corners_pixel"]["near_right"] == [1540, 770]
    assert "guide_path" not in payload


def test_calibration_payload_includes_point_order() -> None:
    payload = calibration_payload(
        VALID_POINTS,
        Path("frame.png"),
        "doubles",
    )

    assert payload["point_order"] == list(CALIBRATION_POINT_ORDER)


def test_image_size_reads_width_height(tmp_path: Path) -> None:
    image_path = tmp_path / "image.png"
    assert cv2.imwrite(str(image_path), np.zeros((30, 40, 3), dtype=np.uint8))

    assert image_size(image_path) == (40, 30)


def test_render_html_uses_unscaled_image_dimensions() -> None:
    html = render_html(1920, 1080)

    assert 'width="1920"' in html
    assert 'height="1080"' in html
    assert "max-width: none" in html
    assert "calibration_guide" not in html
    assert "Guía de calibración" not in html
