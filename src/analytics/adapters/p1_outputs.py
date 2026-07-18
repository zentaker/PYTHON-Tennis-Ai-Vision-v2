"""Strict read-only loaders for accepted serialized P1 outputs."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any

from ..contracts import AnalyticsEventInput, ConfidenceValue, ContactContext, EvidenceItem, PlayerContextSample


class P1OutputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AcceptedP1Contact:
    event: AnalyticsEventInput
    player: PlayerContextSample
    contact: ContactContext
    pose: dict[str, Any]
    position: dict[str, Any]
    audit: dict[str, Any]
    evidence: tuple[EvidenceItem, ...]


def _read_json(path: Path) -> Any:
    if not path.is_file():
        raise P1OutputError(f"missing required file: {path}")
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise P1OutputError(f"invalid JSON in {path}: {exc}") from exc


def _confidence(value: Any, path: Path, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise P1OutputError(f"{path}: invalid {field}") from exc
    if not isfinite(result) or not 0 <= result <= 1:
        raise P1OutputError(f"{path}: {field} must be finite in [0,1]")
    return result


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise P1OutputError(f"missing required file: {path}")
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _key(row: dict[str, Any], path: Path) -> tuple[int, str]:
    try:
        frame = int(row["frame_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise P1OutputError(f"{path}: frame_id must be an integer") from exc
    track = str(row.get("track_id", "")).strip()
    if not track:
        raise P1OutputError(f"{path}: track_id must be non-empty")
    return frame, track


def _finite_number(value: Any, path: Path, event_id: str, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise P1OutputError(f"{path}: {event_id} invalid {field}") from exc
    if not isfinite(result):
        raise P1OutputError(f"{path}: {event_id} non-finite {field}")
    return result


def load_accepted_p1_contacts(results_dir: Path) -> tuple[AcceptedP1Contact, ...]:
    tracks_path = results_dir / "selected_player_tracks.csv"
    poses_path = results_dir / "selected_player_pose.jsonl"
    positions_path = results_dir / "selected_player_court_positions.csv"
    contacts_path = results_dir / "selected_contact_audit.json"
    timestamp_path = results_dir / "perception_report.json"
    if not timestamp_path.is_file():
        timestamp_path = results_dir.parent / "gpu-retest-raw/perception_report.json"

    tracks: dict[tuple[int, str], dict[str, Any]] = {}
    identities: set[tuple[int, str]] = set()
    for row in _rows(tracks_path):
        key = _key(row, tracks_path)
        identity = row.get("selected_identity") or row.get("identity")
        if identity not in {"near", "far"}:
            raise P1OutputError(f"{tracks_path}: {key} identity must be near/far")
        if (key[0], identity) in identities:
            raise P1OutputError(f"{tracks_path}: duplicate {identity} track at frame {key[0]}")
        if key in tracks:
            raise P1OutputError(f"{tracks_path}: duplicate track {key}")
        identities.add((key[0], identity))
        row["selected_identity"] = identity
        _confidence(row.get("confidence"), tracks_path, "confidence")
        tracks[key] = row

    poses: dict[tuple[int, str], dict[str, Any]] = {}
    if not poses_path.is_file():
        raise P1OutputError(f"missing required file: {poses_path}")
    for line_number, line in enumerate(poses_path.read_text().splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise P1OutputError(f"{poses_path}:{line_number}: invalid JSON") from exc
        key = _key(row, poses_path)
        if len(row.get("keypoints", [])) != 133:
            raise P1OutputError(f"{poses_path}: {key} requires exactly 133 keypoints")
        names = {item.get("name") for item in row["keypoints"]}
        if not {"left_wrist", "right_wrist"} <= names:
            raise P1OutputError(f"{poses_path}: {key} wrists missing")
        if key in poses:
            raise P1OutputError(f"{poses_path}: duplicate pose {key}")
        _confidence(row.get("confidence"), poses_path, "confidence")
        poses[key] = row

    positions: dict[tuple[int, str], dict[str, Any]] = {}
    for row in _rows(positions_path):
        key = _key(row, positions_path)
        if key in positions:
            raise P1OutputError(f"{positions_path}: duplicate court position {key}")
        _confidence(row.get("confidence"), positions_path, "confidence")
        for field in ("x_m", "y_m"):
            try:
                value = float(row[field])
            except (KeyError, ValueError) as exc:
                raise P1OutputError(f"{positions_path}: {key} invalid {field}") from exc
            if not isfinite(value):
                raise P1OutputError(f"{positions_path}: {key} non-finite {field}")
            row[field] = value
        positions[key] = row

    perception = _read_json(timestamp_path)
    timestamps = {int(frame["frame_id"]): float(frame["timestamp_seconds"]) for frame in perception["frames"]}
    if any(not isfinite(value) for value in timestamps.values()):
        raise P1OutputError(f"{timestamp_path}: timestamp_seconds must be finite")

    contacts = _read_json(contacts_path)
    seen: set[str] = set()
    output: list[AcceptedP1Contact] = []
    for audit in sorted(contacts, key=lambda item: (int(item["frame_id"]), str(item["event_id"]))):
        event_id = str(audit.get("event_id", "")).strip()
        if not event_id or event_id in seen:
            raise P1OutputError(f"{contacts_path}: duplicate or empty event_id {event_id!r}")
        seen.add(event_id)
        key = _key(audit, contacts_path)
        identity = audit.get("identity")
        if identity not in {"near", "far"} or audit.get("expected_player") != identity:
            raise P1OutputError(f"{contacts_path}: {event_id} mismatched identity")
        if key not in tracks:
            raise P1OutputError(f"{contacts_path}: {event_id} missing track {key}")
        if tracks[key]["selected_identity"] != identity:
            raise P1OutputError(f"{contacts_path}: {event_id} contact-to-track mismatch")
        if key not in poses:
            raise P1OutputError(f"{contacts_path}: {event_id} missing pose {key}")
        if key not in positions:
            raise P1OutputError(f"{contacts_path}: {event_id} missing court position {key}")
        if key[0] not in timestamps:
            raise P1OutputError(f"{timestamp_path}: {event_id} missing real timestamp")
        confidence = _confidence(audit.get("confidence"), contacts_path, "confidence")
        selection_score = _confidence(
            audit.get("selection_score"), contacts_path, "selection_score"
        )
        distance = _finite_number(
            audit.get("ball_wrist_distance_px"),
            contacts_path,
            event_id,
            "ball_wrist_distance_px",
        )
        for field in ("ball_pixel",):
            values = audit.get(field)
            if not isinstance(values, list) or len(values) != 2:
                raise P1OutputError(f"{contacts_path}: {event_id} invalid {field}")
            for index, value in enumerate(values):
                _finite_number(value, contacts_path, event_id, f"{field}[{index}]")
        wrist_pixels = audit.get("wrist_pixels")
        if not isinstance(wrist_pixels, dict):
            raise P1OutputError(f"{contacts_path}: {event_id} invalid wrist_pixels")
        for wrist in ("left_wrist", "right_wrist"):
            values = wrist_pixels.get(wrist)
            if not isinstance(values, list) or len(values) != 2:
                raise P1OutputError(f"{contacts_path}: {event_id} invalid wrist_pixels.{wrist}")
            for index, value in enumerate(values):
                _finite_number(value, contacts_path, event_id, f"wrist_pixels.{wrist}[{index}]")
        position = positions[key]
        player = PlayerContextSample(timestamps[key[0]], key[1], identity, position["x_m"], position["y_m"], confidence)
        contact = ContactContext(event_id, key[1], key[0], distance, ConfidenceValue("p1_contact_audit", "ball_to_wrist", confidence, tuple(audit.get("warnings", [])), model_inferred=True, geometry_derived=True))
        event = AnalyticsEventInput(event_id, timestamps[key[0]], key[0])
        evidence = (
            EvidenceItem("p1_player_selection", "court_player_selector", f"selected {identity} identity", selection_score, model_inferred=True, geometry_derived=True),
            EvidenceItem("p1_player_tracks", "accepted_track", f"accepted track {key[1]}", _confidence(tracks[key]["confidence"], tracks_path, "confidence"), model_inferred=True),
            EvidenceItem("p1_player_pose", "rtmpose_wholebody", "133-keypoint pose", float(poses[key].get("confidence", 0)), model_inferred=True),
            EvidenceItem("p1_court_position", "homography_projection", "court position", _confidence(position["confidence"], positions_path, "confidence"), geometry_derived=True),
            EvidenceItem("p1_contact_audit", "ball_to_wrist", "contact-to-wrist evidence", confidence, model_inferred=True, geometry_derived=True),
        )
        output.append(AcceptedP1Contact(event, player, contact, poses[key], position, audit, evidence))
    return tuple(output)
