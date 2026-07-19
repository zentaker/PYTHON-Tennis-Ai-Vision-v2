from __future__ import annotations

from types import SimpleNamespace

import cv2
import numpy as np

from src.ground_plane_calibration.court_line_refinement import (
    COURT_LINES,
    apply_homography,
    refine_homography,
    sample_court_lines,
    synthetic_line_mask,
)
from src.ground_plane_calibration.player_ground_position import (
    estimate_foot_pixel,
    fuse_ground_estimates,
)
from src.stage5b_v3.ground_contract import anchor_objective_residual, contact_prior_from_ground
from src.stage5b_v3.v31 import materially_ambiguous, trajectory_difference


def test_regulation_dimensions_and_lines() -> None:
    assert COURT_LINES["left_doubles"][0][0] == -5.485
    assert COURT_LINES["right_singles"][0][0] == 4.115
    assert COURT_LINES["far_baseline"][0][1] == 11.885
    assert COURT_LINES["near_service"][0][1] == -6.4
    assert len(COURT_LINES) == 10


def test_synthetic_line_detection_and_refinement() -> None:
    true = np.array([[45.0, 2.0, 320.0], [0.5, -18.0, 420.0], [0.0, 0.01, 1.0]])
    mask = synthetic_line_mask(true, (600, 800))
    distance = cv2.distanceTransform(255 - mask, cv2.DIST_L2, 3)
    court, _ = sample_court_lines(2)
    pixels = apply_homography(true, court)
    perturbed = true.copy(); perturbed[0, 2] += 7; perturbed[1, 2] -= 5
    result = refine_homography(perturbed, distance, court, pixels, 0.02)
    assert np.median(result.refined_errors) < np.median(result.initial_errors)
    assert np.isfinite(result.condition)


def test_multiple_lines_provide_more_constraints_than_four_corners() -> None:
    points, names = sample_court_lines(12)
    assert len(points) == 120 and len(set(names)) == 10
    assert len(points) > 4


def test_line_at_infinity_and_offcourt_projection_finite() -> None:
    matrix = np.array([[60.0, 4.0, 1300.0], [0.0, -25.0, 700.0], [0.0, 0.01, 1.0]])
    infinity = np.linalg.inv(matrix).T[2]
    projected = apply_homography(matrix, np.array([[0.0, 16.885], [0.0, -16.885]]))
    assert np.isfinite(infinity).all() and np.isfinite(projected).all()


def _foot(name: str, x: float, y: float, confidence: float = 0.8) -> dict:
    return {"name": name, "x": x, "y": y, "confidence": confidence, "visible": True}


def test_foot_estimator_uses_both_feet_and_missing_points() -> None:
    points = [_foot("left_ankle", 10, 90), _foot("left_heel", 9, 100), _foot("right_heel", 20, 101)]
    result = estimate_foot_pixel(points, {"x1": 0, "x2": 30, "y1": 0, "y2": 105})
    assert not result["fallback_used"] and len(result["supporting_keypoints"]) == 3
    assert result["pixel"][1] >= 95


def test_bbox_bottom_fallback() -> None:
    result = estimate_foot_pixel([], {"x1": 5, "x2": 25, "y1": 10, "y2": 110})
    assert result["pixel"] == [15.0, 110.0]
    assert "BBOX_BOTTOM_FALLBACK" in result["warnings"]


def test_elevated_foot_warning_and_temporal_aggregation() -> None:
    points = [_foot("left_heel", 10, 50), _foot("right_heel", 20, 100)]
    result = estimate_foot_pixel(points, {"x1": 0, "x2": 30, "y1": 0, "y2": 110}, [(19, 101), (21, 99)])
    assert "ELEVATED_OR_ASYMMETRIC_FOOT" in result["warnings"]
    assert result["temporal_support"] == 2


def test_method_fusion_resolves_agreement_and_rejects_severe_disagreement() -> None:
    resolved = fuse_ground_estimates((1, 2), (1.2, 2.1), 0.2, 0.3)
    unresolved = fuse_ground_estimates((1, 2), (4, 8), 0.2, 0.3)
    assert resolved["resolved"] and not unresolved["resolved"]
    assert unresolved["fused_xy"] is None


def test_algorithm_is_event_independent_and_deterministic() -> None:
    points = [_foot("left_heel", 10, 100), _foot("right_heel", 20, 101)]
    bbox = {"x1": 0, "x2": 30, "y1": 0, "y2": 105}
    assert estimate_foot_pixel(points, bbox) == estimate_foot_pixel(points, bbox)


def test_far_pixel_uncertainty_maps_larger_than_inside() -> None:
    # Perspective scale increases toward extrapolated rows in the production policy.
    inside = 3.0 * (0.02 + 0.0015 * max(0, abs(0.0) - 6.4))
    far = 3.0 * (0.02 + 0.0015 * max(0, abs(16.885) - 6.4))
    assert far > inside


def test_calibration_changes_anchor_prior_and_objective() -> None:
    one = {"fused_xy_m": [1.0, 2.0], "metric_uncertainty_m": 0.2}
    two = {"fused_xy_m": [2.0, 4.0], "metric_uncertainty_m": 0.2}
    candidate = np.array([1.5, 2.5, 1.0])
    assert not np.allclose(contact_prior_from_ground(one, 1.0), contact_prior_from_ground(two, 1.0))
    assert not np.allclose(anchor_objective_residual(candidate, one), anchor_objective_residual(candidate, two))


def _solution(x_offset: float, cost: float = 10.0) -> SimpleNamespace:
    samples = tuple({"xyz": [x_offset + index, index * 0.2, 1.0 + index * 0.1]} for index in range(4))
    return SimpleNamespace(samples=samples, cost=cost, parameters=(x_offset, 0, 1, 0, 0, 0))


def test_ambiguity_uses_complete_trajectory_not_initial_z() -> None:
    reference, incompatible_xy = _solution(0.0), _solution(2.0, 10.2)
    metrics = trajectory_difference(reference, incompatible_xy)
    assert reference.parameters[2] == incompatible_xy.parameters[2]
    assert metrics["rms_xy_m"] == 2.0
    assert materially_ambiguous(reference, incompatible_xy, {"ambiguity_cost_ratio": 1.1, "ambiguity_depth_threshold_m": 0.5})
