from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from src.court.render_top_view import (
    court_line_segments,
    render_calibration_clicks_preview,
    render_court_2d_top,
    sample_segment,
)


def test_court_line_segments_include_expected_lines() -> None:
    names = {name for name, _start, _end in court_line_segments()}

    assert "far_baseline" in names
    assert "near_baseline" in names
    assert "net_left_half" in names
    assert "center_service_far" in names


def test_sample_segment_returns_requested_number_of_points() -> None:
    points = sample_segment((0.0, 0.0), (10.0, 0.0), samples=5)

    assert points.shape == (5, 2)
    assert points[0].tolist() == [0.0, 0.0]
    assert points[-1].tolist() == [10.0, 0.0]


def test_render_court_2d_top_writes_image(tmp_path: Path) -> None:
    output_path = tmp_path / "court.png"

    render_court_2d_top(output_path)

    image = cv2.imread(str(output_path))
    assert image is not None
    assert image.shape[0] > 100
    assert image.shape[1] > 100
    assert np.std(image) > 0


def test_render_calibration_clicks_preview_writes_labeled_image(tmp_path: Path) -> None:
    frame_path = tmp_path / "frame.png"
    corners_path = tmp_path / "corners.json"
    output_path = tmp_path / "preview.png"
    assert cv2.imwrite(str(frame_path), np.zeros((400, 800, 3), dtype=np.uint8))
    points = {
        "far_left": [250, 80],
        "far_right": [550, 80],
        "near_left": [100, 350],
        "near_right": [700, 350],
        "far_left_service": [300, 140],
        "far_right_service": [500, 140],
        "near_left_service": [220, 280],
        "near_right_service": [580, 280],
    }
    corners_path.write_text(json.dumps({"court_corners_pixel": points}), encoding="utf-8")

    render_calibration_clicks_preview(frame_path, corners_path, output_path)

    preview = cv2.imread(str(output_path))
    assert preview is not None
    assert np.count_nonzero(preview) > 0
