#!/usr/bin/env python3
"""Validate a P1 artifact directory without judging visual accuracy."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


REQUIRED = (
    "player_tracks.csv",
    "player_pose.jsonl",
    "player_court_positions.csv",
    "contact_audit.json",
    "perception_report.json",
    "artifact_manifest.json",
)


def validate(output_dir: Path, expected_frames: list[int] | None = None) -> dict[str, object]:
    missing = [name for name in REQUIRED if not (output_dir / name).is_file()]
    if missing:
        raise ValueError(f"missing required output files: {missing}")
    report = json.loads((output_dir / "perception_report.json").read_text(encoding="utf-8"))
    frame_ids = [int(frame["frame_id"]) for frame in report.get("frames", [])]
    if expected_frames is not None and frame_ids != expected_frames:
        raise ValueError(f"report frame IDs {frame_ids} do not match expected {expected_frames}")
    if any(float(frame.get("timestamp_seconds", -1)) < 0 for frame in report.get("frames", [])):
        raise ValueError("report contains missing or negative timestamps")
    with (output_dir / "player_tracks.csv").open(newline="", encoding="utf-8") as handle:
        tracks = list(csv.DictReader(handle))
    with (output_dir / "player_court_positions.csv").open(newline="", encoding="utf-8") as handle:
        positions = list(csv.DictReader(handle))
    if report.get("frame_count") != len(frame_ids):
        raise ValueError("report frame_count is inconsistent")
    if not tracks or not positions:
        raise ValueError("track and court position outputs must not be empty")
    audits = json.loads((output_dir / "contact_audit.json").read_text(encoding="utf-8"))
    if not isinstance(audits, list):
        raise ValueError("contact_audit.json must contain a list")
    artifacts = json.loads((output_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    if artifacts.get("schema_version") != "1.0":
        raise ValueError("artifact manifest schema version is invalid")
    return {
        "status": "VALID",
        "frames": frame_ids,
        "track_rows": len(tracks),
        "audit_rows": len(audits),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--frames", help="comma-separated expected frame IDs")
    args = parser.parse_args()
    expected = [int(item) for item in args.frames.split(",")] if args.frames else None
    print(json.dumps(validate(args.output_dir, expected), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
