from __future__ import annotations

from typing import Any


def derive_metrics(
    session_id: str,
    rally_id: str,
    start: float,
    end: float,
    track: list[dict[str, Any]],
    events: list[dict[str, Any]],
    limitations: list[str],
) -> dict[str, Any]:
    contacts = [item for item in events if item["event_type"] == "contact"]
    bounces = [item for item in events if item["event_type"] == "bounce"]
    near = sum(item["player"] == "near" for item in contacts)
    far = sum(item["player"] == "far" for item in contacts)
    unknown = len(contacts) - near - far
    quality = "high" if track and events else "low"
    if any(item["confidence"] is None for item in events):
        quality = "medium"
    return {
        "schema_version": "metrics.v1",
        "session_id": session_id,
        "rally_id": rally_id,
        "duration_seconds": end - start,
        "ball_observations": len(track),
        "contacts": len(contacts),
        "bounces": len(bounces),
        "near_player_contacts": near,
        "far_player_contacts": far,
        "unknown_player_contacts": unknown,
        "data_quality": quality,
        "limitations": list(limitations),
    }
