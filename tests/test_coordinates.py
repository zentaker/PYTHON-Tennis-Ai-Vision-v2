from __future__ import annotations

import pytest

from src.court.coordinates import (
    CALIBRATION_POINT_ORDER,
    COURT_DIMENSIONS,
    calibration_court_points,
)


def test_court_dimensions_match_project_convention() -> None:
    assert COURT_DIMENSIONS.total_length_m == pytest.approx(23.77)
    assert COURT_DIMENSIONS.half_length_m == pytest.approx(11.885)
    assert COURT_DIMENSIONS.singles_half_width_m == pytest.approx(4.115)
    assert COURT_DIMENSIONS.doubles_half_width_m == pytest.approx(5.485)
    assert COURT_DIMENSIONS.service_line_distance_m == pytest.approx(6.40)


@pytest.mark.parametrize("layout, expected_corner_x", [("doubles", 5.485), ("singles", 4.115)])
def test_calibration_points_are_symmetric(layout: str, expected_corner_x: float) -> None:
    points = calibration_court_points(layout)  # type: ignore[arg-type]

    assert tuple(points) == CALIBRATION_POINT_ORDER
    assert points["far_left"][0] == pytest.approx(-expected_corner_x)
    assert points["far_right"][0] == pytest.approx(expected_corner_x)
    assert points["near_left"][0] == pytest.approx(-expected_corner_x)
    assert points["near_right"][0] == pytest.approx(expected_corner_x)

    symmetric_pairs = (
        ("far_left", "far_right"),
        ("near_left", "near_right"),
        ("far_left_service", "far_right_service"),
        ("near_left_service", "near_right_service"),
    )
    for left, right in symmetric_pairs:
        assert points[left][0] + points[right][0] == pytest.approx(0.0)


def test_service_points_use_singles_width_for_both_layouts() -> None:
    for layout in ("doubles", "singles"):
        points = calibration_court_points(layout)
        assert points["far_left_service"] == pytest.approx((-4.115, 6.40))
        assert points["far_right_service"] == pytest.approx((4.115, 6.40))
        assert points["near_left_service"] == pytest.approx((-4.115, -6.40))
        assert points["near_right_service"] == pytest.approx((4.115, -6.40))


def test_invalid_layout_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported calibration layout"):
        calibration_court_points("mini")  # type: ignore[arg-type]
