from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import numpy as np

from src.ground_plane_calibration.anchor_v4 import temporal_motion_status, total_anchor_uncertainty
from src.stage5b_v3.v32 import load_anchor_v4

ROOT = Path(__file__).parents[1]


def test_static_acceptance_is_independent_of_temporal_speed() -> None:
    assert temporal_motion_status({"longest_valid_chain": 12, "p95_speed_mps": 20}) == "unresolved"
    report = json.loads((ROOT / "config/stage5b_v3/stage5b_v32_anchor_v4_report.json").read_text())
    assert report["contact_anchor_status"] == "accepted_observation" and report["anchors"] == 5


def test_temporal_warnings_are_preserved_without_invalidating_anchors() -> None:
    report = json.loads((ROOT / "config/stage5b_v3/stage5b_v32_anchor_v4_report.json").read_text())
    events = report["events"]
    assert events["ev_003"]["temporal_motion_status"] == "unresolved"
    assert events["ev_009"]["temporal_motion_status"] == "unresolved"
    assert events["ev_007"]["temporal_motion_status"] == "insufficient_chain"
    assert report["contact_anchor_status"] == "accepted_observation"


def test_total_uncertainty_is_deterministic_and_uses_static_sources() -> None:
    positions = np.array([[1.0, 2.0], [1.3, 2.2], [0.8, 1.9]])
    args = (positions, np.array([1.0, 2.0]), 0.3, 2.0, 0.04, 6.0)
    one = total_anchor_uncertainty(*args, far_player=False, seed=42)
    two = total_anchor_uncertainty(*args, far_player=False, seed=42)
    assert one == two and one["uncertainty_x_m"] >= 0.4
    wider_foot = total_anchor_uncertainty(positions, args[1], 1.2, 2.0, 0.04, 6.0, far_player=False, seed=42)
    wider_cycle = total_anchor_uncertainty(positions, args[1], 0.3, 8.0, 0.04, 6.0, far_player=False, seed=42)
    no_spread = total_anchor_uncertainty(np.repeat([[1.0, 2.0]], 3, axis=0), args[1], 0.3, 2.0, 0.04, 6.0, far_player=False, seed=42)
    assert wider_foot["uncertainty_x_m"] > one["uncertainty_x_m"]
    assert wider_cycle["uncertainty_y_m"] > one["uncertainty_y_m"]
    assert np.ptp(one["calibration_ci95"], axis=0).max() > np.ptp(no_spread["calibration_ci95"], axis=0).max()


def test_v4_schema_and_exactly_five_accepted_records() -> None:
    report = json.loads((ROOT / "config/stage5b_v3/stage5b_v32_anchor_v4_report.json").read_text())
    path = ROOT / report["path"]
    schema = json.loads((ROOT / "config/ground_plane_calibration/player_contact_ground_anchor_v4.schema.json").read_text())
    assert report["anchors"] == 5
    assert {"contact_anchor_status", "temporal_motion_status", "total_ci95"} <= set(schema["required"])
    if path.exists():
        anchors = load_anchor_v4(path)
        for row in anchors.values():
            jsonschema.validate(row, schema)
        assert len(anchors) == 5


def test_general_algorithm_has_no_event_hardcoding_or_distance_cap() -> None:
    source = (ROOT / "src/ground_plane_calibration/anchor_v4.py").read_text()
    assert "ev_003" not in source and "ev_009" not in source
    assert "distance_cap" not in source and "player displacement" in source


def test_v32_real_result_contact_bounce_and_schema_contract() -> None:
    result = json.loads((ROOT / "config/stage5b_v3/stage5b_v32_result.json").read_text())
    assert result["contacts_consumed"] == 5 and result["observations_consumed"] == 314
    assert result["negative_z_violations"] == 0
    assert result["maximum_bounce_residual_m"] < 0.05
    assert result["schema_valid_samples"] == 314
    assert result["status"] == "STAGE5B_V32_REJECTED_BY_HUMAN_GATE"
