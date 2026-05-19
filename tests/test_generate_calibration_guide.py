from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from src.court.generate_calibration_guide import (
    GUIDE_POINTS_APPROX,
    draw_calibration_guide,
    generate_calibration_guide,
)


def test_guide_points_use_expected_order() -> None:
    assert list(GUIDE_POINTS_APPROX) == list(range(1, 9))
    assert GUIDE_POINTS_APPROX[1][0] == "far_left"
    assert GUIDE_POINTS_APPROX[8][0] == "near_right_service"


def test_draw_calibration_guide_returns_annotated_copy() -> None:
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    guide = draw_calibration_guide(image)

    assert guide.shape == image.shape
    assert guide.sum() > 0
    assert image.sum() == 0


def test_generate_calibration_guide_writes_file(tmp_path: Path) -> None:
    image_path = tmp_path / "frame.png"
    output_path = tmp_path / "guide.png"
    assert cv2.imwrite(str(image_path), np.zeros((80, 120, 3), dtype=np.uint8))

    generate_calibration_guide(image_path, output_path)

    assert output_path.exists()
