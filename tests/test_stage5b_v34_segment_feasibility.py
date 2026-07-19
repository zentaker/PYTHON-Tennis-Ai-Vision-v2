from __future__ import annotations

from src.stage5b_v3.event_node_graph import analytic_ballistic_candidate


def test_analytic_ballistic_feasibility_and_exact_endpoints() -> None:
    result = analytic_ballistic_candidate([0, -10, 1.5], [0, 10, 0], 1.2)
    assert result["feasible"] and result["negative_z_count"] == 0
    assert result["sampled_xyz"][0] == [0.0, -10.0, 1.5]
    assert result["sampled_xyz"][-1][2] == 0.0


def test_impossible_duration_and_net_constraint_rejected() -> None:
    assert not analytic_ballistic_candidate([0, 0, 1], [1, 1, 1], 0)["feasible"]
    low = analytic_ballistic_candidate([0, -1, 0.1], [0, 1, 0.1], 0.1)
    assert not low["feasible"]


def test_negative_z_and_speed_gate() -> None:
    result = analytic_ballistic_candidate([0, 0, -1], [0, 1, -1], 1)
    assert not result["feasible"] and result["negative_z_count"] > 0
    fast = analytic_ballistic_candidate([0, 0, 1], [100, 0, 1], 0.1)
    assert not fast["feasible"]
