from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from src.ground_plane_calibration.temporal_validation import (
    classify_segments,
    detect_line_segments,
    far_evidence_decision,
    ground_region_mask,
    optical_flow_step,
    support_foot_candidates,
)


def test_real_and_synthetic_segment_detection_excludes_outside_logo() -> None:
    image = np.zeros((200, 300), dtype=np.uint8)
    cv2.line(image, (20, 100), (280, 100), 255, 3)
    cv2.line(image, (20, 20), (280, 20), 255, 3)
    mask = np.zeros_like(image)
    mask[60:180] = 255
    segments = detect_line_segments(image, mask, 20)
    assert segments and all(np.mean(row["endpoints"], axis=0)[1] >= 60 for row in segments)


def test_line_family_classification_and_net_exclusion() -> None:
    segments = [{"endpoints": [[10, 50], [190, 50]], "length_px": 180, "orientation_deg": 0}]
    model = {"near_baseline": np.array([[0, 52], [200, 52]]), "net": np.array([[0, 50], [200, 50]])}
    result = classify_segments(segments, model)
    assert result[0]["line_family_candidate"] == "near_baseline"
    assert result[0]["accepted"]


def test_ground_region_validation() -> None:
    mask = ground_region_mask((100, 100), np.array([[10, 10], [90, 10], [80, 90], [20, 90]]))
    assert mask[50, 50] and not mask[0, 0]


def test_optical_flow_forward_backward_consistency() -> None:
    first = np.zeros((120, 120), dtype=np.uint8)
    second = first.copy()
    cv2.circle(first, (50, 60), 6, 255, -1)
    cv2.circle(second, (54, 63), 6, 255, -1)
    points = np.array([[[50.0, 60.0]]], dtype=np.float32)
    result = optical_flow_step(first, second, points)
    assert result["support"] == 1 and result["fb_error"] <= 1.5
    assert np.allclose(result["displacement"], [4, 3], atol=0.8)


def test_temporal_drift_rejection() -> None:
    blank = np.zeros((80, 80), dtype=np.uint8)
    result = optical_flow_step(blank, blank, np.array([[[10.0, 10.0]]], dtype=np.float32))
    assert result["support"] == 0 and np.isinf(result["fb_error"])


def _point(name: str, x: float, y: float, confidence: float = 0.8) -> dict:
    return {"name": name, "x": x, "y": y, "confidence": confidence, "visible": True}


def test_support_foot_selection_rejects_elevated_foot() -> None:
    points = [_point("left_heel", 10, 70), _point("right_heel", 20, 100)]
    result = support_foot_candidates(points, {"x1": 0, "x2": 30, "y1": 0, "y2": 105})
    assert result["selected_side"] == "right" and not result["ambiguous"]


def test_both_feet_ambiguity_is_preserved() -> None:
    points = [_point("left_heel", 10, 100), _point("right_heel", 20, 101)]
    result = support_foot_candidates(points, {"x1": 0, "x2": 30, "y1": 0, "y2": 105})
    assert result["ambiguous"] and "FOOT_SUPPORT_AMBIGUOUS" in result["warnings"]


def test_far_position_has_no_fixed_five_metre_gate() -> None:
    assert far_evidence_decision(True, 30, 0, 0.5, 80) == "accepted_observation"


def test_far_position_unresolved_when_families_disagree() -> None:
    assert far_evidence_decision(True, 30, 0, 3.0, 80) == "unresolved"


def test_correlated_geometry_and_leave_out_are_serialized() -> None:
    runner = (Path(__file__).parents[1] / "scripts/run_stage5a2b_temporal_ground.py").read_text()
    assert '"correlated_geometry_sources": True' in runner
    assert "leave_far_family_out" in runner and "leave_near_family_out" in runner


def test_no_personal_path_or_fixed_far_gate_in_versioned_cli() -> None:
    runner = (Path(__file__).parents[1] / "scripts/run_stage5a2b_temporal_ground.py").read_text()
    assert "/Users/" not in runner and "Desktop/" not in runner
    assert 'far_distance_gate_m": None' in runner


def test_auto_expanded_visual_has_no_fixed_far_clipping() -> None:
    runner = (Path(__file__).parents[1] / "scripts/run_stage5a2b_temporal_ground.py").read_text()
    assert "all_y.min()" in runner and "all_y.max()" in runner and "ax.set_ylim" in runner


def test_deterministic_far_decision() -> None:
    inputs = (True, 20, 0, 0.4, 40)
    assert far_evidence_decision(*inputs) == far_evidence_decision(*inputs)
