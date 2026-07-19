"""Canonical event timeline and explicit flight topology for Stage 5B v3.3."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def canonical_timeline(annotation_path: Path) -> list[dict[str, Any]]:
    annotation = json.loads(annotation_path.read_text())
    events = annotation["narrative_events"]
    if len(events) != 10:
        raise ValueError("canonical timeline requires five contacts and five bounces")
    rows: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        event_type = "bounce" if event["type"] == "bounce" else "contact"
        rows.append(
            {
                "event_id": event["id"],
                "event_type": event_type,
                "frame_id": int(event["frame_start"]),
                "timestamp_seconds": float(event["time_start_seconds"]),
                "player_identity": event["player"] if event_type == "contact" else None,
                "source": event["source"],
                "confidence": 1.0,
                "previous_event_id": events[index - 1]["id"] if index else None,
                "next_event_id": events[index + 1]["id"] if index + 1 < len(events) else None,
            }
        )
    validate_timeline(rows)
    return rows


def validate_timeline(rows: list[dict[str, Any]]) -> None:
    ids = [row["event_id"] for row in rows]
    times = [row["timestamp_seconds"] for row in rows]
    frames = [row["frame_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate event")
    if any(right <= left for left, right in zip(times, times[1:], strict=False)):
        raise ValueError("timestamps are not strictly increasing")
    if any(right <= left for left, right in zip(frames, frames[1:], strict=False)):
        raise ValueError("frames are not strictly increasing")
    if sum(row["event_type"] == "contact" for row in rows) != 5:
        raise ValueError("missing contact event")
    if sum(row["event_type"] == "bounce" for row in rows) != 5:
        raise ValueError("missing bounce event")


def load_observations(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="") as handle:
        return [
            {"frame_id": int(row["frame_id"]), "timestamp_seconds": float(row["timestamp_seconds"])}
            for row in csv.DictReader(handle)
            if row.get("x_smooth")
            and row.get("y_smooth")
            and row.get("is_outlier", "false").lower() != "true"
        ]


def build_segment_topology(
    timeline: list[dict[str, Any]], observations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    validate_timeline(timeline)
    segments: list[dict[str, Any]] = []
    assigned: set[int] = set()
    for index, (start, end) in enumerate(zip(timeline, timeline[1:], strict=False), 1):
        selected = [
            row
            for row in observations
            if start["timestamp_seconds"] <= row["timestamp_seconds"]
            and (
                row["timestamp_seconds"] < end["timestamp_seconds"]
                or (index == 9 and row["timestamp_seconds"] <= end["timestamp_seconds"])
            )
        ]
        overlap = assigned.intersection(row["frame_id"] for row in selected)
        if overlap:
            raise ValueError(f"observation overlap: {sorted(overlap)}")
        assigned.update(row["frame_id"] for row in selected)
        expected = "contact_volume" if start["event_type"] == "contact" else "bounce_z0"
        expected += "+contact_volume" if end["event_type"] == "contact" else "+bounce_z0"
        segments.append(
            {
                "segment_id": f"flight_{index:02d}",
                "start_event_id": start["event_id"],
                "start_event_type": start["event_type"],
                "start_frame": start["frame_id"],
                "start_timestamp": start["timestamp_seconds"],
                "end_event_id": end["event_id"],
                "end_event_type": end["event_type"],
                "end_frame": end["frame_id"],
                "end_timestamp": end["timestamp_seconds"],
                "observations_first_frame": selected[0]["frame_id"] if selected else None,
                "observations_last_frame": selected[-1]["frame_id"] if selected else None,
                "observations_count": len(selected),
                "direction": f"{start.get('player_identity') or 'court'}_to_{end.get('player_identity') or 'court'}",
                "expected_endpoint_constraints": expected,
                "gaps": max(0, end["frame_id"] - start["frame_id"] + 1 - len(selected)),
                "topology_status": "PASS" if selected and end["timestamp_seconds"] > start["timestamp_seconds"] else "FAIL",
            }
        )
    if len(segments) != 9:
        raise ValueError("exactly nine flights required")
    return segments
