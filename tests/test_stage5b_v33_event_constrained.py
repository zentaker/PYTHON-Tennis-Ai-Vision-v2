from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.optimize import least_squares

from src.stage5b_v3.contact_volume import (
    build_contact_volume,
    contact_volume_metrics,
    normalized_contact_residual,
)
from src.stage5b_v3.event_topology import (
    build_segment_topology,
    canonical_timeline,
    load_observations,
    validate_timeline,
)

ROOT = Path(__file__).parents[1]
ANNOTATION = ROOT / "data/clips/nivel_a2_01/manual_annotation.json"
BALL = ROOT / "tests/fixtures/stage5b_v3/smoothed_trajectory_real.csv"


def timeline() -> list[dict]:
    return canonical_timeline(ANNOTATION)


def sample_anchor() -> dict:
    return {"event_id": "contact", "identity": "near", "fused_x_m": 0.0, "fused_y_m": -12.0, "total_ci95": [[-0.5, -12.5], [0.5, -11.5]]}


def sample_pose() -> dict:
    names = ("left_wrist", "right_wrist", "left_shoulder", "right_shoulder", "left_hip", "right_hip")
    return {"keypoints": [{"name": name, "x": 100 + i, "y": 200 + i, "confidence": 0.8, "visible": True} for i, name in enumerate(names)]}


def test_canonical_order_and_exact_topology() -> None:
    events = timeline()
    topology = build_segment_topology(events, load_observations(BALL))
    assert len(events) == 10 and len(topology) == 9
    assert all(row["topology_status"] == "PASS" for row in topology)
    assert sum(row["observations_count"] for row in topology) == 314
    assert topology[0]["start_event_id"] == "ev_001" and topology[-1]["end_event_id"] == "ev_010"


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "reversed"])
def test_invalid_event_timelines_rejected(mutation: str) -> None:
    events = copy.deepcopy(timeline())
    if mutation == "duplicate":
        events[1]["event_id"] = events[0]["event_id"]
    elif mutation == "missing":
        events.pop()
    else:
        events[2]["timestamp_seconds"] = events[1]["timestamp_seconds"] - 1
    with pytest.raises(ValueError):
        validate_timeline(events)


def test_contact_mapping_endpoint_side_and_frames() -> None:
    topology = build_segment_topology(timeline(), load_observations(BALL))
    assert topology[0]["start_event_type"] == "contact"
    assert topology[1]["end_event_type"] == "contact"
    contacts = {row["start_event_id"] for row in topology if row["start_event_type"] == "contact"}
    contacts |= {row["end_event_id"] for row in topology if row["end_event_type"] == "contact"}
    assert contacts == {"ev_001", "ev_003", "ev_005", "ev_007", "ev_009"}
    assert all(row["observations_first_frame"] == row["start_frame"] for row in topology)


def test_foot_anchor_is_not_exact_ball_contact_and_volume_uses_pose() -> None:
    volume = build_contact_volume(sample_anchor(), sample_pose(), (120.0, 190.0))
    assert volume["player_ground_anchor"][2] == 0
    assert volume["feasible_vertical_range_m"][0] > 0
    assert len(volume["wrist_ray_candidates"]) == 2 and volume["racket_extension_m"] > 0


def test_contact_volume_excess_and_constraint_influence() -> None:
    volume = build_contact_volume(sample_anchor(), sample_pose(), (120.0, 190.0))
    inside = [0.0, -12.0, 1.5]
    outside = [8.0, -12.0, 1.5]
    assert contact_volume_metrics(inside, volume)["contact_volume_excess_m"] == 0
    assert contact_volume_metrics(outside, volume)["contact_volume_excess_m"] > 0
    moved = sample_anchor() | {"fused_x_m": 1.0, "total_ci95": [[0.5, -12.5], [1.5, -11.5]]}
    moved_volume = build_contact_volume(moved, sample_pose(), (120.0, 190.0))
    assert not np.array_equal(normalized_contact_residual(outside, volume), normalized_contact_residual(outside, moved_volume))


def test_anchor_changes_reduced_optimized_endpoint() -> None:
    target = np.array([3.0, -12.0, 1.5])
    one = build_contact_volume(sample_anchor(), sample_pose(), (120.0, 190.0))
    moved = sample_anchor() | {"fused_x_m": 1.0, "total_ci95": [[0.5, -12.5], [1.5, -11.5]]}
    two = build_contact_volume(moved, sample_pose(), (120.0, 190.0))
    solve = lambda volume: least_squares(lambda p: np.r_[p - target, 10 * normalized_contact_residual(p, volume)], target).x
    assert np.linalg.norm(solve(one) - solve(two)) > 0.1


def test_uncertainty_racket_height_and_wrong_mapping_affect_feasibility() -> None:
    anchor = sample_anchor()
    point = [2.4, -12.0, 3.8]
    base = build_contact_volume(anchor, sample_pose(), (1, 1), racket_extension_m=0.4)
    racket = build_contact_volume(anchor, sample_pose(), (1, 1), racket_extension_m=1.0)
    higher = build_contact_volume(anchor, sample_pose(), (1, 1), height_range_m=(0.3, 4.2))
    assert contact_volume_metrics(point, base) != contact_volume_metrics(point, racket)
    assert contact_volume_metrics(point, higher)["contact_volume_excess_m"] < contact_volume_metrics(point, base)["contact_volume_excess_m"]
    wrong = build_contact_volume(anchor | {"fused_y_m": 12.0, "total_ci95": [[-0.5, 11.5], [0.5, 12.5]]}, sample_pose(), (1, 1))
    assert contact_volume_metrics([0, -12, 1], wrong)["contact_volume_excess_m"] > 10


def test_normalization_prevents_term_count_from_changing_contact_scale() -> None:
    volume = build_contact_volume(sample_anchor(), sample_pose(), (1, 1))
    residual = normalized_contact_residual([4, -12, 1], volume)
    assert np.allclose(residual, normalized_contact_residual([4, -12, 1], volume))
    assert np.linalg.norm(residual) == pytest.approx(np.linalg.norm(np.tile(residual, (314, 1))[0]))


def test_no_event_specific_hardcoding_and_determinism() -> None:
    source = (ROOT / "src/stage5b_v3/contact_volume.py").read_text()
    assert "ev_" not in source
    assert build_segment_topology(timeline(), load_observations(BALL)) == build_segment_topology(timeline(), load_observations(BALL))
