"""Evaluate every declared event frame/range; never silently collapse to frame_start."""

from __future__ import annotations

from typing import Any


def declared_event_frames(event: dict[str, Any]) -> list[int]:
    frames = event.get("frame_range") or list(range(event["frame_start"], event["frame_end"] + 1))
    return sorted(set(int(frame) for frame in frames))


def timing_candidates(
    annotation: dict[str, Any],
    observations: dict[int, dict[str, Any]],
    audits: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates = []
    for event in annotation["narrative_events"]:
        for frame_id in declared_event_frames(event):
            observation = observations.get(frame_id)
            audit = audits.get(event["id"], {})
            if observation is None:
                continue
            distance = audit.get("ball_wrist_distance_px")
            candidates.append(
                {
                    "event_id": event["id"],
                    "event_type": "bounce" if event["type"] == "bounce" else "contact",
                    "frame_id": frame_id,
                    "frame_start": event["frame_start"],
                    "frame_end": event["frame_end"],
                    "timestamp_seconds": observation["timestamp_seconds"],
                    "raw_pixel": observation.get("raw_pixel"),
                    "smoothed_pixel": observation.get("smoothed_pixel"),
                    "ball_wrist_distance_px": distance,
                    "confidence": observation.get("confidence", 0.0),
                    "timing_prior": 0.0 if frame_id == event["frame_start"] else -0.25,
                    "selection_reason": "declared_frame_range",
                }
            )
    return candidates
