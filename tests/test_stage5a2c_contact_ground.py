from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from src.ground_plane_calibration.court_line_refinement import COURT_LINES, apply_homography
from src.ground_plane_calibration.line_constrained_ensemble import (
    RADIAL_DISTORTION_STATUS,
    fit_line_constrained_homography,
    identifiable,
    real_family_subsets,
)
from src.ground_plane_calibration.sequential_player_tracker import (
    sequential_chain,
    track_adjacent_step,
    valid_speed_diagnostics,
)


def synthetic_segments(matrix: np.ndarray) -> list[dict]:
    rows = []
    for family in (
        "left_doubles",
        "right_doubles",
        "near_baseline",
        "far_baseline",
        "near_service",
    ):
        pixels = apply_homography(matrix, np.asarray(COURT_LINES[family]))
        delta = pixels[1] - pixels[0]
        rows.append(
            {
                "accepted": True,
                "line_family_candidate": family,
                "endpoints": pixels.tolist(),
                "length_px": float(np.linalg.norm(delta)),
                "orientation_deg": float(np.degrees(np.arctan2(delta[1], delta[0])) % 180),
            }
        )
    return rows


def geometry() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    matrix = np.array([[45.0, 2.0, 320.0], [0.5, -18.0, 420.0], [0.0, 0.01, 1.0]])
    court = np.array(
        [
            [-5.485, -11.885],
            [5.485, -11.885],
            [-5.485, 11.885],
            [5.485, 11.885],
            [-4.115, -6.4],
            [4.115, -6.4],
            [-4.115, 6.4],
            [4.115, 6.4],
        ]
    )
    return matrix, court, apply_homography(matrix, court)


def test_real_segments_affect_optimized_homography() -> None:
    true, court, pixels = geometry()
    initial = true.copy()
    initial[0, 2] += 6
    fit = fit_line_constrained_homography(initial, synthetic_segments(true), court, pixels)
    assert not np.allclose(fit["H_court_to_pixel"], initial) and fit["segments_used"] == 5


def test_removing_segment_changes_calibration() -> None:
    true, court, pixels = geometry()
    rows = synthetic_segments(true)
    rows[0]["endpoints"][0][0] += 3
    first = fit_line_constrained_homography(true, rows, court, pixels)
    second = fit_line_constrained_homography(true, rows[1:], court, pixels)
    assert not np.allclose(first["H_court_to_pixel"], second["H_court_to_pixel"])


def test_real_family_definitions_and_insufficient_geometry() -> None:
    true, _, _ = geometry()
    rows = synthetic_segments(true)
    families = real_family_subsets(rows)
    assert "baselines_plus_sidelines" in families and "deterministic_subset_mod2" in families
    assert not identifiable([row for row in rows if "baseline" in row["line_family_candidate"]])
    with pytest.raises(ValueError):
        fit_line_constrained_homography(true, rows[:2], np.zeros((4, 2)), np.zeros((4, 2)))


def test_radial_metadata_cannot_claim_unexecuted_hypothesis() -> None:
    assert RADIAL_DISTORTION_STATUS == "RADIAL_DISTORTION_NOT_IDENTIFIABLE_FROM_CURRENT_INPUTS"


def moving_pair() -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    first = np.zeros((160, 160), np.uint8)
    second = np.zeros_like(first)
    for x in (55, 65, 75):
        for y in (80, 90, 100):
            cv2.circle(first, (x, y), 2, 255, -1)
            cv2.circle(second, (x + 2, y + 1), 2, 255, -1)
    points = np.array([[[x, y]] for x in (55, 65, 75) for y in (80, 90, 100)], np.float32)
    return first, second, points, {"x1": 45, "y1": 60, "x2": 90, "y2": 120}


def test_adjacent_flow_updates_bbox_and_uses_ransac() -> None:
    first, second, points, bbox = moving_pair()
    result = track_adjacent_step(first, second, points, bbox, (70, 105))
    assert result["valid"] and result["inlier_count"] >= 4
    assert result["bbox"]["x1"] > bbox["x1"] and "affine" in result


def test_forward_backward_chains_update_reference() -> None:
    first, second, _, bbox = moving_pair()
    frames = {10: first, 11: second}
    chain = sequential_chain(frames, 10, bbox, (70, 105), 1)
    assert chain[0]["reference_frame_id"] == 10 and chain[0]["frame_id"] == 11


def test_drift_terminates_without_zero_displacement() -> None:
    blank = np.zeros((100, 100), np.uint8)
    result = track_adjacent_step(
        blank,
        blank,
        np.empty((0, 1, 2), np.float32),
        {"x1": 1, "y1": 1, "x2": 20, "y2": 30},
        (10, 25),
    )
    assert not result["valid"] and "foot_pixel" not in result


def test_invalid_frames_excluded_from_pts_speed() -> None:
    rows = [
        {"valid": True, "frame_id": 1, "chain_direction": "forward", "ground_xy": [0, 0]},
        {"valid": False, "frame_id": 2, "chain_direction": "forward", "ground_xy": [100, 0]},
        {"valid": True, "frame_id": 3, "chain_direction": "forward", "ground_xy": [0.1, 0]},
    ]
    result = valid_speed_diagnostics(rows, {1: 0.0, 2: 0.04, 3: 0.08})
    assert result["valid_speed_samples"] == 0 and result["rejected_transitions"] == 1


def test_valid_speed_uses_real_timestamps() -> None:
    rows = [
        {"valid": True, "frame_id": 1, "chain_direction": "forward", "ground_xy": [0, 0]},
        {"valid": True, "frame_id": 2, "chain_direction": "forward", "ground_xy": [0.1, 0]},
    ]
    result = valid_speed_diagnostics(rows, {1: 1.0, 2: 1.05})
    assert result["maximum_valid_speed_mps"] == pytest.approx(2.0)


def test_no_distance_cap_and_ev_independent_runner() -> None:
    source = (Path(__file__).parents[1] / "scripts/run_stage5a2c_contact_ground.py").read_text()
    assert 'baseline_distance_median"] <' not in source
    algorithm = source.split('fig, axes = plt.subplots(1, 2')[0]
    assert "ev_003" not in algorithm and "ev_007" not in algorithm
    assert "contact-args.temporal_radius" in source or "contact - args.temporal_radius" in source


def test_distant_drift_does_not_enter_local_window_policy() -> None:
    source = (Path(__file__).parents[1] / "scripts/run_stage5a2c_contact_ground.py").read_text()
    assert 'abs(row["frame_id"] - contact) <= 5' in source


def test_deterministic_line_fit() -> None:
    true, court, pixels = geometry()
    rows = synthetic_segments(true)
    one = fit_line_constrained_homography(true, rows, court, pixels)
    two = fit_line_constrained_homography(true, rows, court, pixels)
    assert np.allclose(one["H_court_to_pixel"], two["H_court_to_pixel"])
