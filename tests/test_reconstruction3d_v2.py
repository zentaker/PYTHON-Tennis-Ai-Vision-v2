from __future__ import annotations

import numpy as np

from src.reconstruction3d_v2.ballistic_segments import endpoint_velocity, trajectory_from_endpoints
from src.reconstruction3d_v2.render_side import canvas_to_world, world_to_canvas
from src.reconstruction3d_v2.render_top import (
    COURT,
    canvas_to_world as top_to_world,
    world_to_canvas as top_to_canvas,
)
from src.reconstruction3d_v2.event_observations import observe_event


def test_endpoint_ballistic_is_exact_and_bounce_is_exact() -> None:
    start = np.array([1.0, -3.0, 1.2])
    end = np.array([-2.0, 4.0, 0.0])
    duration = 0.8
    velocity = endpoint_velocity(start, end, duration)
    assert np.linalg.norm(trajectory_from_endpoints(start, end, duration, 0.0) - start) <= 1e-8
    assert np.linalg.norm(trajectory_from_endpoints(start, end, duration, duration) - end) <= 1e-8
    assert abs(end[2]) <= 1e-8
    assert velocity[2] > 0


def test_top_view_isotropic_and_far_up() -> None:
    x0 = top_to_canvas(0, 0)
    x1 = top_to_canvas(1, 0)
    y1 = top_to_canvas(0, 1)
    far = top_to_canvas(0, COURT["baseline"])
    near = top_to_canvas(0, -COURT["baseline"])
    assert abs(abs(x1[0] - x0[0]) - abs(y1[1] - x0[1])) <= 1
    assert far[1] < near[1]
    assert np.allclose(top_to_world(*top_to_canvas(2.0, 8.0)), [2.0, 8.0], atol=0.02)


def test_side_view_keeps_points_behind_baseline() -> None:
    canvas = world_to_canvas(13.0, 2.0)
    y, z = canvas_to_world(*canvas)
    assert y > 11.885
    assert z > 0


def test_event_observation_does_not_search_beyond_two_frames() -> None:
    rows = [
        {"timestamp_seconds": str(i), "x_smooth": "", "y_smooth": "", "confidence": "0"}
        for i in range(8)
    ]
    rows[0].update(x_smooth="10", y_smooth="20", confidence="1")
    rows[6].update(x_smooth="30", y_smooth="40", confidence="1")
    event = {"id": "ev", "frame_start": 3, "frame_end": 3}
    result = observe_event(rows, event, 3)
    assert not result.valid
    assert "within_two_frames" in result.reason
