from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from src.court.calibrate_interactive import (
    build_calibration_payload,
    draw_points,
    save_calibration_outputs,
)
from src.court.coordinates import CALIBRATION_POINT_ORDER


def sample_points() -> dict[str, tuple[int, int]]:
    return {name: (index * 10, index * 20) for index, name in enumerate(CALIBRATION_POINT_ORDER)}


def test_build_calibration_payload_preserves_point_order(tmp_path: Path) -> None:
    payload = build_calibration_payload(sample_points(), tmp_path / "frame.png", "doubles")

    assert payload["layout"] == "doubles"
    assert payload["point_order"] == list(CALIBRATION_POINT_ORDER)
    assert payload["court_corners_pixel"]["far_left"] == [0, 0]  # type: ignore[index]


def test_build_calibration_payload_rejects_missing_points(tmp_path: Path) -> None:
    points = sample_points()
    points.pop("near_right_service")

    with pytest.raises(ValueError, match="near_right_service"):
        build_calibration_payload(points, tmp_path / "frame.png", "doubles")


def test_save_calibration_outputs_writes_json_and_preview(tmp_path: Path) -> None:
    image = np.zeros((120, 160, 3), dtype=np.uint8)
    json_output = tmp_path / "court_corners_pixel.json"
    preview_output = tmp_path / "preview.png"

    save_calibration_outputs(
        image,
        sample_points(),
        tmp_path / "frame.png",
        json_output,
        preview_output,
        "singles",
    )

    assert json_output.exists()
    assert preview_output.exists()
    preview = cv2.imread(str(preview_output))
    assert preview is not None
    assert preview.sum() > 0


def test_draw_points_does_not_mutate_source_image() -> None:
    image = np.zeros((120, 160, 3), dtype=np.uint8)
    _preview = draw_points(image, sample_points())

    assert image.sum() == 0
