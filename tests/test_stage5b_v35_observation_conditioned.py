from __future__ import annotations

import json
from pathlib import Path

from src.stage5b_v3.body_constrained_contact import body_contact_candidates
from src.stage5b_v3.observation_conditioned_edges import score_edge
from src.geometry.camera_model import CameraModel

ROOT = Path(__file__).parents[1]
OUT = ROOT / ".artifacts/stage5b-v35-observation-conditioned/output"


def test_body_contact_is_anchor_linked_and_not_uncertainty_reach() -> None:
    pose = json.loads(
        (ROOT / "tests/fixtures/integration/p1_analytics_accepted/selected_player_pose.jsonl")
        .read_text()
        .splitlines()[0]
    )
    anchor = json.loads(
        (
                ROOT / "config/ground_plane_calibration/player_contact_ground_anchors_v4.jsonl"
        )
        .read_text()
        .splitlines()[0]
    )
    result = body_contact_candidates(
        CameraModel.read_json(ROOT / "tests/fixtures/stage5b_v3/camera_model_refined.json"),
        pose,
        anchor,
        (1512, 647),
    )
    assert result["candidates"] and "anchor_mahalanobis_cost" in result["candidates"][0]
    assert result["candidates"][0]["racket_length_m"] > 0


def test_all_interior_observations_affect_edge_cost() -> None:
    camera = CameraModel.read_json(ROOT / "tests/fixtures/stage5b_v3/camera_model_refined.json")
    start = {"timestamp_seconds": 0.0, "xyz": [0, -10, 1]}
    end = {"timestamp_seconds": 1.0, "xyz": [0, 10, 0]}
    observations = [
        {"timestamp_seconds": 0.1, "pixel": [1000, 700], "confidence": 0.9},
        {"timestamp_seconds": 0.2, "pixel": [1200, 700], "confidence": 0.9},
    ]
    base = score_edge(camera, start, end, observations)
    changed = score_edge(
        camera,
        start,
        end,
        observations + [{"timestamp_seconds": 0.3, "pixel": [2500, 1400], "confidence": 0.9}],
    )
    assert base["observation_conditioned"] and len(changed["train_errors_px"]) > len(base["train_errors_px"])


def test_speed_only_selection_is_removed_and_models_holdout() -> None:
    edge = json.loads((OUT / "stage5b_v35_edge_costs.json").read_text())[0]
    assert edge["selection_basis"] != "speed_only"
    assert edge["models"][0]["holdout_p95_px"] is not None
    report = json.loads((OUT / "stage5b_v35_run_report.json").read_text())
    assert report["gate_a_status"] == "STAGE5B_V35_OBSERVATION_CONDITIONED_NODES_PARTIAL"
    assert report["gate_b_executed"] is False


def test_per_segment_states_and_no_old_xyz_dependency() -> None:
    segments = json.loads((OUT / "stage5b_v35_segments.json").read_text())
    assert len(segments) == 9
    source = (ROOT / "scripts/run_stage5b_v35_observation_conditioned.py").read_text()
    assert "stage5b_v32_xyz" not in source and "/Users/" not in source
