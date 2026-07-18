import json
from pathlib import Path

import pytest

from src.analytics.contracts import BallTrajectorySample
from src.analytics.kinematics import estimate_event_kinematics, estimate_speed


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


def test_contact_windows_keep_incoming_and_outgoing_independent_with_vfr():
    result = estimate_event_kinematics(
        load("contact_vfr"), 0.5, "court_planar_xy",
        pre_window_seconds=0.5, post_window_seconds=0.5,
    )
    assert result.incoming_speed_mps == pytest.approx(10.0)
    assert result.outgoing_speed_mps == pytest.approx(20.0)
    assert result.incoming_samples_used == 5
    assert result.outgoing_samples_used == 5
    assert result.speed_at_net_kmh is None
    assert result.speed_before_bounce_kmh is None
    assert result.speed_after_bounce_kmh is None


@pytest.mark.parametrize(("side", "index"), [("incoming", 2), ("outgoing", 6)])
def test_contact_windows_reject_outlier_on_only_its_side(side, index):
    samples = load("contact_vfr")
    sample = samples[index]
    samples[index] = BallTrajectorySample(
        sample.timestamp_seconds, 100.0, sample.y, coordinate_unit="metres"
    )
    result = estimate_event_kinematics(samples, 0.5, "court_planar_xy")
    assert getattr(result, f"{side}_rejected_samples") > 0
    other = "outgoing" if side == "incoming" else "incoming"
    expected = 20.0 if other == "outgoing" else 10.0
    assert getattr(result, f"{other}_speed_mps") == pytest.approx(expected)


def test_gap_or_insufficient_evidence_is_unavailable_per_side():
    samples = load("contact_vfr")
    result = estimate_event_kinematics(
        samples, 0.5, "court_planar_xy", pre_window_seconds=0.05
    )
    assert result.incoming_speed_mps is None
    assert result.incoming_samples_used == 0
    assert result.outgoing_speed_mps == pytest.approx(20.0)
    after_missing = estimate_event_kinematics(
        samples, 0.5, "court_planar_xy", post_window_seconds=0.05
    )
    assert after_missing.outgoing_speed_mps is None
    one_side_gap = estimate_event_kinematics(
        samples, 0.5, "court_planar_xy", max_gap_seconds=0.1
    )
    assert one_side_gap.incoming_rejected_samples > 0


def test_contact_outside_range_and_planar_vs_3d():
    samples = load("contact_vfr")
    outside = estimate_event_kinematics(samples, 2.0, "court_planar_xy")
    assert outside.status == "unavailable"
    assert outside.incoming_speed_mps is None and outside.outgoing_speed_mps is None
    no_z = estimate_event_kinematics(samples, 0.5, "estimated_3d")
    assert no_z.status == "unavailable"
