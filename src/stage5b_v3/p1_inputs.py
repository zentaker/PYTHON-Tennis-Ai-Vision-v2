"""Independent read-only loader for the accepted P1 contact subset."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class P1ContactInput:
    event_id: str
    frame_id: int
    timestamp_seconds: float
    track_id: str
    identity: str
    player_x_m: float
    player_y_m: float
    pose: dict[str, Any]
    audit: dict[str, Any]


def load_p1_contacts(path: Path) -> tuple[P1ContactInput, ...]:
    contacts = json.loads((path / "selected_contact_audit.json").read_text())
    poses = {
        (int(row["frame_id"]), row["track_id"]): row
        for row in (
            json.loads(line)
            for line in (path / "selected_player_pose.jsonl").read_text().splitlines()
        )
    }
    with (path / "selected_player_court_positions.csv").open(newline="") as handle:
        positions = {
            (int(row["frame_id"]), row["track_id"]): row for row in csv.DictReader(handle)
        }
    timestamp_path = path / "perception_report.json"
    if not timestamp_path.is_file():
        timestamp_path = path.parent / "gpu-retest-raw/perception_report.json"
    timestamps = {
        int(row["frame_id"]): float(row["timestamp_seconds"])
        for row in json.loads(timestamp_path.read_text())["frames"]
    }
    output = []
    seen = set()
    for audit in sorted(contacts, key=lambda row: (int(row["frame_id"]), row["event_id"])):
        event_id = str(audit["event_id"])
        if event_id in seen:
            raise ValueError(f"duplicate P1 event_id: {event_id}")
        seen.add(event_id)
        frame_id, track_id = int(audit["frame_id"]), str(audit["track_id"])
        identity = str(audit["identity"])
        if identity not in {"near", "far"}:
            raise ValueError(f"{event_id}: invalid player identity")
        key = (frame_id, track_id)
        if key not in poses or key not in positions or frame_id not in timestamps:
            raise ValueError(f"{event_id}: incomplete accepted P1 context")
        if len(poses[key].get("keypoints", [])) != 133:
            raise ValueError(f"{event_id}: pose must contain 133 keypoints")
        output.append(
            P1ContactInput(
                event_id,
                frame_id,
                timestamps[frame_id],
                track_id,
                identity,
                float(positions[key]["x_m"]),
                float(positions[key]["y_m"]),
                poses[key],
                audit,
            )
        )
    return tuple(output)
