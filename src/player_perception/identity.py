"""Temporal near/far identity assignment from court support points."""

from __future__ import annotations

from .schemas import PlayerTrack


def assign_near_far(
    tracks: list[PlayerTrack],
    court_y_by_track: dict[str, float],
    previous: dict[str, str] | None = None,
) -> list[PlayerTrack]:
    previous = previous or {}
    result = []
    for track in tracks:
        y = court_y_by_track.get(track.track_id)
        identity = previous.get(track.track_id)
        if identity is None and y is not None:
            identity = "near" if y < 0 else "far" if y > 0 else "unknown"
        result.append(
            PlayerTrack(
                track.frame_id, track.track_id, track.bbox, identity or "unknown", track.confidence
            )
        )
    return result


def stable_identity_history(
    history: dict[str, list[str]], *, minimum_consistent: int = 2
) -> dict[str, str]:
    assignments = {}
    for track_id, labels in history.items():
        near = labels.count("near")
        far = labels.count("far")
        if max(near, far) >= minimum_consistent and near != far:
            assignments[track_id] = "near" if near > far else "far"
        else:
            assignments[track_id] = "unknown"
    return assignments
