from __future__ import annotations

import copy
from pathlib import Path

import numpy as np

from src.geometry.camera_model import CameraModel
from src.stage5b_v3.contact_ray_feasibility import (
    point_on_ray_at_height,
    round_trip_error,
    solve_contact_ray,
)

ROOT = Path(__file__).parents[1]


def camera() -> CameraModel:
    return CameraModel.read_json(ROOT / "tests/fixtures/stage5b_v3/camera_model_refined.json")


def anchor() -> dict:
    return {
        "event_id": "generic",
        "fused_x_m": 1.0,
        "fused_y_m": -11.0,
        "total_ci95": [[0.0, -12.0], [2.0, -10.0]],
    }


def test_ball_and_wrist_ray_round_trip() -> None:
    model = camera()
    assert round_trip_error(model, (1512.0, 647.0), 1.5) < 1e-6
    point, distance = point_on_ray_at_height(model, (1569.0, 742.0), 1.5)
    assert distance > 0 and np.isfinite(point).all()


def test_inputs_change_ray_manifold() -> None:
    model = camera()
    wrists = {"left": (1562.0, 928.0), "right": (1569.0, 742.0)}
    base = solve_contact_ray(model, (1512.0, 647.0), wrists, anchor())
    moved_ball = solve_contact_ray(model, (1530.0, 647.0), wrists, anchor())
    moved_wrist = solve_contact_ray(model, (1512.0, 647.0), {"right": (1600.0, 742.0)}, anchor())
    moved_anchor = copy.deepcopy(anchor())
    moved_anchor["fused_x_m"] += 2
    moved_anchor["total_ci95"] = [[2, -12], [4, -10]]
    moved_ground = solve_contact_ray(model, (1512.0, 647.0), wrists, moved_anchor)
    assert base["ball_ray"]["direction"] != moved_ball["ball_ray"]["direction"]
    assert base["wrist_rays"] != moved_wrist["wrist_rays"]
    assert (
        base["player_ground_anchor_distribution"]
        != moved_ground["player_ground_anchor_distribution"]
    )


def test_racket_camera_height_and_missing_wrist_influence() -> None:
    model = camera()
    wrists = {"left": (1562.0, 928.0), "right": (1569.0, 742.0)}
    short = solve_contact_ray(model, (1512.0, 647.0), wrists, anchor(), racket_length_m=0.1)
    long = solve_contact_ray(model, (1512.0, 647.0), wrists, anchor(), racket_length_m=1.2)
    high = solve_contact_ray(model, (1512.0, 647.0), wrists, anchor(), height_range_m=(2.5, 3.2))
    one = solve_contact_ray(model, (1512.0, 647.0), {"right": wrists["right"]}, anchor())
    assert len(long["candidate_3d_contact_points"]) >= len(short["candidate_3d_contact_points"])
    assert high["candidate_3d_contact_points"] != long["candidate_3d_contact_points"]
    assert "left" not in one["wrist_rays"]


def test_camera_change_changes_contact_ray() -> None:
    first = camera()
    second = camera()
    second.t = second.t + np.array([0.1, 0.0, 0.0])
    args = ((1512.0, 647.0), {"right": (1569.0, 742.0)}, anchor())
    assert (
        solve_contact_ray(first, *args)["ball_ray"]["origin"]
        != solve_contact_ray(second, *args)["ball_ray"]["origin"]
    )
