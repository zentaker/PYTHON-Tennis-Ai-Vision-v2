import json
from pathlib import Path

import pytest

from src.analytics.contracts import BallTrajectorySample
from src.analytics.kinematics import estimate_speed


def load(name, *, unit="metres"):
    values = json.loads(Path(f"tests/fixtures/analytics/{name}.json").read_text())
    return [BallTrajectorySample(**value, coordinate_unit=unit) for value in values]


@pytest.mark.parametrize("fixture", ["planar_linear", "vfr_irregular"])
def test_planar_speed_uses_vfr_and_converts_units(fixture):
    result = estimate_speed(load(fixture), "court_planar_xy")
    assert result.outgoing_speed_mps == pytest.approx(5.0)
    assert result.outgoing_speed_kmh == pytest.approx(18.0)
    assert "not real 3D" in result.warnings[-1]


def test_3d_speed_requires_z_and_computes_known_synthetic_value():
    result = estimate_speed(load("trajectory_3d"), "estimated_3d")
    assert result.outgoing_speed_mps == pytest.approx(13.0)
    unavailable = estimate_speed(load("planar_linear"), "estimated_3d")
    assert unavailable.status == "unavailable"


def test_invalid_timestamps_and_gaps_are_not_fabricated():
    invalid = estimate_speed(load("invalid_timestamps"), "court_planar_xy")
    assert invalid.status == "unavailable" and invalid.outgoing_speed_kmh is None
    gap = estimate_speed(load("with_gap"), "court_planar_xy")
    assert gap.rejected_samples == 1
    assert gap.outgoing_speed_mps == pytest.approx(5.0)


def test_outliers_and_pixel_diagnostics():
    result = estimate_speed(load("with_outlier"), "court_planar_xy")
    assert result.outgoing_speed_mps == pytest.approx(5.0)
    pixel = estimate_speed(load("planar_linear", unit="pixels"), "pixel_apparent")
    assert pixel.speed_unit == "pixels_per_second"
    assert pixel.outgoing_speed_mps is None and pixel.outgoing_speed_kmh is None
