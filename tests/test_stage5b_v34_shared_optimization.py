from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_phase_a_has_no_old_xyz_or_personal_path_dependency() -> None:
    source = (ROOT / "scripts/run_stage5b_v34_contact_ray_feasibility.py").read_text()
    phase_a = source.split("def run_phase_b", 1)[0]
    assert "stage5b_v32_xyz" not in phase_a
    assert "stage5b_v31_xyz" not in phase_a
    assert "/Users/" not in source


def test_shared_equality_is_structural_and_contact_manifold_is_bounded() -> None:
    source = (ROOT / "src/stage5b_v3/event_node_graph.py").read_text()
    assert "start_node_reference" in source and "end_node_reference" in source
    ray_source = (ROOT / "src/stage5b_v3/contact_ray_feasibility.py").read_text()
    assert "candidate_3d_contact_points" in ray_source and "event_id']" not in ray_source


def test_deterministic_general_algorithms_without_event_hardcoding() -> None:
    for name in ("contact_pixel_reconciliation.py", "contact_ray_feasibility.py"):
        source = (ROOT / "src/stage5b_v3" / name).read_text()
        assert "ev_00" not in source and "/Users/" not in source
