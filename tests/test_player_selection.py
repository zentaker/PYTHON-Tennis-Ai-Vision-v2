from __future__ import annotations

from src.player_perception.player_selection import (
    PlayerCandidate,
    SelectionState,
    court_distance,
    select_court_players,
)

SIZE = (2746, 1536)


def candidate(track: str, x: float, y: float, *, box=(1000, 700, 1120, 1150), confidence=0.8, presence=0.8, contact=False):
    return PlayerCandidate(track.replace("track", "det"), track, 1, box, confidence, x, y, 0.7, presence, contact)


def test_inside_player_beats_spectator_and_multiple_spectators() -> None:
    result = select_court_players(
        [candidate("track_player", 0, -10), candidate("track_left", -11, -8), candidate("track_right", 10, -5)],
        SelectionState(), SIZE,
    )
    assert result.near.original_track_id == "track_player"
    assert sum(item.selected_identity is None for item in result.decisions) == 2


def test_selects_one_near_and_one_far() -> None:
    result = select_court_players(
        [candidate("near", 1, -10), candidate("far", -3, 18, box=(900, 150, 1000, 310))],
        SelectionState(), SIZE,
    )
    assert result.near.original_track_id == "near"
    assert result.far.original_track_id == "far"


def test_missing_candidate_does_not_fill_with_spectator() -> None:
    result = select_court_players([candidate("spectator", -12, 15)], SelectionState(), SIZE)
    assert result.near is result.far is None
    assert "outside_lateral_play_area" in result.decisions[0].rejection_reasons


def test_temporal_stability_prefers_existing_track() -> None:
    state = SelectionState()
    first = select_court_players([candidate("stable", 0, -10)], state, SIZE)
    second = select_court_players(
        [candidate("stable", 0.2, -10, confidence=0.7), candidate("new", 0, -10, confidence=0.75)], state, SIZE
    )
    assert first.near.original_track_id == second.near.original_track_id == "stable"


def test_tie_is_reproducible_by_track_id() -> None:
    items = [candidate("track_b", 0, -10), candidate("track_a", 0, -10)]
    assert select_court_players(items, SelectionState(), SIZE).near.original_track_id == "track_a"
    assert select_court_players(reversed(items), SelectionState(), SIZE).near.original_track_id == "track_a"


def test_implausible_bbox_and_far_outside_court_are_rejected() -> None:
    tiny = candidate("tiny", 0, -10, box=(100, 100, 101, 101))
    outside = candidate("outside", 0, 25, box=(900, 150, 1000, 310))
    result = select_court_players([tiny, outside], SelectionState(), SIZE)
    assert result.near is result.far is None
    assert court_distance(0, 25) > 8


def test_contact_compatibility_is_supporting_not_overriding_geometry() -> None:
    valid = candidate("valid", -3, 18, box=(900, 150, 1000, 310))
    spectator = candidate("contact_spectator", -12, 15, box=(300, 100, 400, 270), contact=True)
    result = select_court_players([valid, spectator], SelectionState(), SIZE)
    assert result.far.original_track_id == "valid"


def test_missing_foot_anchor_is_rejected() -> None:
    item = PlayerCandidate("det", "track", 1, (1000, 700, 1120, 1150), 0.8, 0, -10, 0.0)
    result = select_court_players([item], SelectionState(), SIZE)
    assert result.near is None
    assert "missing_foot_anchor" in result.decisions[0].rejection_reasons


def test_smoke_shaped_fixture_preserves_pose_contract() -> None:
    pose = {"track_id": "track_0001", "keypoints": [{"name": f"point_{i}"} for i in range(133)]}
    result = select_court_players([candidate("track_0001", 1.16, -10.78)], SelectionState(), SIZE)
    assert result.near.original_track_id == pose["track_id"]
    assert len(pose["keypoints"]) == 133
