from __future__ import annotations

import numpy as np

from src.reconstruction3d.ballistic import (
    GRAVITY_M_S2,
    ballistic_position,
    ballistic_velocity,
    net_crossing,
)
from src.reconstruction3d.event_frames import enumerate_event_frame_combinations
from src.reconstruction3d.observations import observation_weight


def test_ballistic_equation_and_gravity() -> None:
    p = ballistic_position([1, 2, 3], [4, 5, 6], 2.0)
    np.testing.assert_allclose(p, [9, 12, 3 + 12 - 0.5 * GRAVITY_M_S2 * 4])
    np.testing.assert_allclose(ballistic_velocity([4, 5, 6], 2.0), [4, 5, 6 - 2 * GRAVITY_M_S2])


def test_net_crossing_and_height() -> None:
    crossing = net_crossing([0, -2, 1], [1, 4, 2], duration=1.0)
    assert crossing is not None
    assert abs(crossing["Y_m"]) < 1e-12
    assert crossing["net_height_m"] >= 0.914


def test_event_frame_combinations_are_exactly_24() -> None:
    events = [
        {"id": "ev_001", "frame_start": 1, "frame_end": 1},
        {"id": "ev_004", "frame_start": 2, "frame_end": 4},
        {"id": "ev_005", "frame_start": 5, "frame_end": 6},
        {"id": "ev_008", "frame_start": 7, "frame_end": 8},
        {"id": "ev_009", "frame_start": 9, "frame_end": 10},
    ]
    combinations = enumerate_event_frame_combinations(events)
    assert len(combinations) == 24
    assert combinations[0]["ev_004"] == 2
    assert combinations[-1]["ev_009"] == 10


def test_observation_weights_preserve_source_semantics() -> None:
    assert observation_weight("detected", 1.0) == 1.0
    assert 0 < observation_weight("interpolated", 0.5) < observation_weight("detected", 0.5)
    assert observation_weight("missing", 1.0) == 0.0
