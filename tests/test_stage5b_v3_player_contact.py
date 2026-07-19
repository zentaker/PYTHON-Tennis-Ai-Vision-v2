from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.geometry.camera_model import CameraModel
from src.stage5b_v3.camera import point_on_pixel_ray_at_height
from src.stage5b_v3.p1_inputs import load_p1_contacts
from src.stage5b_v3.player_contact_anchor import contact_hypotheses


FIXTURE = Path("tests/fixtures/stage5b_v3")
P1 = Path("tests/fixtures/integration/p1_analytics_accepted")


def test_camera_projection_backprojection_and_vertical_anchor() -> None:
    camera = CameraModel.read_json(FIXTURE / "camera_model_refined.json")
    world = np.array([1.0, -8.0, 1.7])
    pixel = camera.project_world_to_pixel([world])[0]
    recovered = point_on_pixel_ray_at_height(camera, tuple(pixel), 1.7)
    assert np.allclose(recovered, world, atol=1e-9)


def test_near_and_far_contacts_evaluate_both_wrists_and_global_reach() -> None:
    camera = CameraModel.read_json(FIXTURE / "camera_model_refined.json")
    config = json.loads(Path("config/stage5b_v3/player_aware_v1.json").read_text())
    contacts = load_p1_contacts(P1)
    assert {item.identity for item in contacts} == {"near", "far"}
    for contact in contacts:
        options = contact_hypotheses(contact, camera, config, 3)
        assert len(options) == 3
        assert all(item.player_identity == contact.identity for item in options)
        assert all(item.ball_ray_constraint_residual_px < 1e-6 for item in options)
        assert all("HITTING_HAND_UNKNOWN_BOTH_WRISTS_EVALUATED" in item.warnings for item in options)


def test_player_identity_is_fail_closed(tmp_path: Path) -> None:
    # The independent loader rejects identity corruption before geometry is attempted.
    import shutil

    target = tmp_path / "p1"
    shutil.copytree(P1, target)
    path = target / "selected_contact_audit.json"
    rows = json.loads(path.read_text())
    rows[0]["identity"] = "spectator"
    path.write_text(json.dumps(rows))
    try:
        load_p1_contacts(target)
    except ValueError as exc:
        assert "invalid player identity" in str(exc)
    else:
        raise AssertionError("invalid identity was accepted")
