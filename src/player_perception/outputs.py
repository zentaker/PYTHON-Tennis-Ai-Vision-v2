"""Versioned writers for player-aware perception artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .contact_audit import audit_contact
from .schemas import FramePerception, PerceptionReport


AUDIT_EVENT_IDS = ("ev_001", "ev_003", "ev_005", "ev_007", "ev_009")


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _frame_map(report: PerceptionReport) -> dict[int, FramePerception]:
    return {frame.frame_id: frame for frame in report.frames}


def build_contact_audit(
    report: PerceptionReport,
    events: Iterable[dict[str, object]],
    trajectory: dict[int, tuple[float, float]] | None = None,
) -> list[dict[str, object]]:
    """Audit the five approved contact events from observed pipeline evidence."""
    frames = _frame_map(report)
    audits: list[dict[str, object]] = []
    for event in events:
        event_id = str(event.get("id", ""))
        if event_id not in AUDIT_EVENT_IDS:
            continue
        frame_id = int(float(event.get("frame_mid", event.get("frame_start", 0))))
        frame = frames.get(frame_id)
        expected = str(event.get("player", event.get("side", "unknown")))
        warnings: list[str] = []
        if frame is None:
            audits.append(
                {"event_id": event_id, "frame_start": frame_id, "warnings": ["frame_not_selected"]}
            )
            continue
        matching = [track for track in frame.tracks if track.identity == expected]
        track = matching[0] if matching else (frame.tracks[0] if frame.tracks else None)
        if track is None:
            audits.append(
                {"event_id": event_id, "frame_start": frame_id, "warnings": ["player_not_visible"]}
            )
            continue
        position = next(
            (item for item in frame.court_positions if item.track_id == track.track_id), None
        )
        anchor = next(
            (item for item in frame.foot_anchors if item.track_id == track.track_id), None
        )
        pose = next((item for item in frame.poses if item.track_id == track.track_id), None)
        ball_pixel = trajectory.get(frame_id) if trajectory else None
        audit = audit_contact(event, track.track_id, position, pose, ball_pixel)
        if track.identity != expected:
            warnings.append("identity_does_not_match_expected_event_side")
        if anchor and anchor.airborne_possible:
            warnings.append("foot_anchor_airborne_possible")
        record = asdict(audit)
        record.update(
            {
                "frame_end": int(event.get("frame_end", frame_id)),
                "bbox": asdict(track.bbox),
                "foot_anchor": asdict(anchor) if anchor else None,
                "identity": track.identity,
                "identity_confidence": track.identity_confidence,
                "identity_reason": track.identity_reason,
                "warnings": list(record.get("warnings", ())) + warnings,
            }
        )
        audits.append(record)
    return audits


def write_perception_outputs(
    report: PerceptionReport,
    output_dir: Path,
    *,
    events: Iterable[dict[str, object]] = (),
    trajectory: dict[int, tuple[float, float]] | None = None,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tracks: list[dict[str, object]] = []
    positions: list[dict[str, object]] = []
    poses: list[dict[str, object]] = []
    for frame in report.frames:
        for track in frame.tracks:
            tracks.append(
                {
                    "frame_id": frame.frame_id,
                    "timestamp_seconds": frame.timestamp_seconds,
                    "track_id": track.track_id,
                    "x1": track.bbox.x1,
                    "y1": track.bbox.y1,
                    "x2": track.bbox.x2,
                    "y2": track.bbox.y2,
                    "bbox_confidence": track.bbox.confidence,
                    "identity": track.identity,
                    "confidence": track.confidence,
                    "identity_confidence": track.identity_confidence,
                    "identity_reason": track.identity_reason,
                    "identity_switch": track.identity_switch,
                    "missing_interval_frames": track.missing_interval_frames,
                    "reassociated": track.reassociated,
                }
            )
        for pose in frame.poses:
            poses.append(
                {
                    "frame_id": frame.frame_id,
                    "timestamp_seconds": frame.timestamp_seconds,
                    **asdict(pose),
                }
            )
        for position in frame.court_positions:
            positions.append(
                {
                    "frame_id": frame.frame_id,
                    "timestamp_seconds": frame.timestamp_seconds,
                    **asdict(position),
                }
            )
    tracks_path = output_dir / "player_tracks.csv"
    _write_csv(
        tracks_path,
        tracks,
        [
            "frame_id",
            "timestamp_seconds",
            "track_id",
            "x1",
            "y1",
            "x2",
            "y2",
            "bbox_confidence",
            "identity",
            "confidence",
            "identity_confidence",
            "identity_reason",
            "identity_switch",
            "missing_interval_frames",
            "reassociated",
        ],
    )
    positions_path = output_dir / "player_court_positions.csv"
    _write_csv(
        positions_path,
        positions,
        [
            "frame_id",
            "timestamp_seconds",
            "track_id",
            "x_m",
            "y_m",
            "confidence",
            "distance_to_near_baseline_m",
            "distance_to_far_baseline_m",
            "inside_court",
            "behind_near_baseline",
            "behind_far_baseline",
            "left_outside",
            "right_outside",
        ],
    )
    pose_path = output_dir / "player_pose.jsonl"
    with pose_path.open("w", encoding="utf-8") as handle:
        for record in poses:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    audits = build_contact_audit(report, events, trajectory)
    audit_path = output_dir / "contact_audit.json"
    audit_path.write_text(json.dumps(audits, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path = output_dir / "perception_report.json"
    report_path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {
        "player_tracks.csv": tracks_path,
        "player_pose.jsonl": pose_path,
        "player_court_positions.csv": positions_path,
        "contact_audit.json": audit_path,
        "perception_report.json": report_path,
    }


def write_artifact_manifest(paths: Iterable[Path], output_dir: Path) -> Path:
    entries = []
    for path in sorted(paths):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append({"path": path.name, "bytes": path.stat().st_size, "sha256": digest})
    manifest = output_dir / "artifact_manifest.json"
    manifest.write_text(
        json.dumps({"schema_version": "1.0", "artifacts": entries}, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
