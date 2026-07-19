from __future__ import annotations

import json
from pathlib import Path

from src.geometry.camera_model import CameraModel
from src.stage5b_v3.p1_inputs import load_p1_contacts
from src.stage5b_v3.player_contact_anchor import contact_hypotheses
from src.stage5b_v3.v31 import reconstruct_v31


CAMERA = Path("tests/fixtures/stage5b_v3/camera_model_refined.json")
BALL = Path("tests/fixtures/stage5b_v3/smoothed_trajectory_real.csv")
EVENTS = Path("data/clips/nivel_a2_01/manual_annotation.json")
P1 = Path("tests/fixtures/integration/p1_analytics_accepted")
CONFIG = Path("config/stage5b_v3/player_aware_v1.json")
H = Path("data/clips/nivel_a2_01/homography.json")


def run(seed: int = 42):
    return reconstruct_v31(CAMERA, H, BALL, EVENTS, P1, CONFIG, seed=seed, starts_per_segment=3)


def test_optimizer_uses_all_observations_and_improves_endpoint_baseline() -> None:
    result = run()
    assert result["observations_in_objective"] == 314
    assert result["optimized_median_error_px"] < 8
    assert result["optimized_median_error_px"] < result["baseline_median_error_px"]
    assert len(result["selected"]) == 9
    assert all(item.observations_in_objective > 0 for item in result["selected"])
    assert {item.segment_id for item in result["solutions"]} == {f"flight_{i:02d}" for i in range(1, 10)}


def test_seed_drives_segment_multistart_but_same_seed_is_deterministic() -> None:
    first, second, other = run(42), run(42), run(43)
    assert first["checksum"] == second["checksum"]

    def by_id(result):
        return {item.hypothesis_id: item for item in result["solutions"]}

    assert by_id(first)["flight_01_h01"].parameters == by_id(second)["flight_01_h01"].parameters
    assert by_id(first)["flight_01_h01"].parameters != by_id(other)["flight_01_h01"].parameters


def test_racket_extension_changes_feasible_contact_score() -> None:
    camera = CameraModel.read_json(CAMERA)
    contact = load_p1_contacts(P1)[0]
    config = json.loads(CONFIG.read_text())
    original = contact_hypotheses(contact, camera, config, 1)[0]
    config["racket_extension_m"] *= 1.5
    changed = contact_hypotheses(contact, camera, config, 1)[0]
    assert changed.contact_confidence != original.contact_confidence
    assert changed.racket_distance_m != 0
    assert changed.ball_ray_constraint_residual_px < 1e-6
    assert changed.wrist_reprojection_error_px < 1e-6


def test_sensitivity_was_executed_and_segment_visuals_do_not_use_global_polyline() -> None:
    result = json.loads(Path("config/stage5b_v3/stage5b_v31_result.json").read_text())
    assert result["sensitivity_runs_executed"] == 9
    source = Path("scripts/run_stage5b_v31_player_aware.py").read_text()
    assert 'if row["segment_id"] == f"flight_{index:02d}"' in source
    assert "global_h" not in source
