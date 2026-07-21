from __future__ import annotations

import hashlib
import json
import math
import tempfile
from pathlib import Path
from typing import Any

import jsonschema

from ..analysis_bundle.builder import build_bundle
from .adapters import (
    adapt_court_map,
    load_ball_track,
    load_events,
    load_frame_timestamps,
    load_json,
)
from .errors import SingleRallyError
from .metrics import derive_metrics
from .validation import validate_single_rally_bundle

ROOT = Path(__file__).parents[3]
INPUT_SCHEMA = ROOT / "config/product/single_rally_inputs_v1.schema.json"


def _safe_input(base: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        if ".." in path.parts:
            raise SingleRallyError(f"unsafe input path: {raw}")
        path = base / path
    if path.is_symlink():
        raise SingleRallyError(f"input symlink rejected: {raw}")
    return path.resolve()


def _event_type(raw: str) -> str:
    return {
        "hit": "contact",
        "contact": "contact",
        "serve": "serve",
        "bounce": "bounce",
        "out": "out",
    }.get(raw, "unknown")


def _event_record(raw: dict[str, Any], rally_id: str) -> dict[str, Any]:
    event_id = raw.get("event_id", raw.get("id"))
    if not isinstance(event_id, str) or not event_id.strip():
        raise SingleRallyError("event_id must be a non-empty string")
    frame_id = raw.get("frame_id", raw.get("frame_start"))
    try:
        frame_id = int(frame_id)
        timestamp = float(raw.get("timestamp_seconds", raw.get("time_start_seconds")))
    except (TypeError, ValueError) as exc:
        raise SingleRallyError(f"event {event_id} lacks frame/timestamp") from exc
    if not math.isfinite(timestamp) or timestamp < 0 or frame_id < 0:
        raise SingleRallyError(f"event {event_id} has invalid frame/timestamp")
    player = raw.get("player", raw.get("side", "unknown"))
    if player not in {"near", "far", "unknown"}:
        player = "unknown"
    confidence = raw.get("confidence")
    if confidence is not None:
        confidence = float(confidence)
        if not 0 <= confidence <= 1:
            raise SingleRallyError(f"event {event_id} confidence is outside [0,1]")
    pixel = raw.get("pixel", raw.get("ball_pixel"))
    if isinstance(pixel, (list, tuple)) and len(pixel) == 2:
        pixel = {"x": float(pixel[0]), "y": float(pixel[1])}
    if pixel is not None and (not isinstance(pixel, dict) or not {"x", "y"}.issubset(pixel)):
        raise SingleRallyError(f"event {event_id} pixel must be [x,y] or {{x,y}}")
    return {
        "schema_version": "event.v1",
        "event_id": event_id,
        "rally_id": rally_id,
        "event_type": _event_type(str(raw.get("event_type", raw.get("type", "unknown")))),
        "timestamp_seconds": timestamp,
        "frame_id": frame_id,
        "player": player,
        "pixel": pixel,
        "court_position": raw.get("court_position"),
        "confidence": confidence,
        "provenance": {
            "source": raw.get("source", "existing_core_output"),
            "source_event_id": event_id,
        },
        "labels": {
            "shot_type": raw.get("shot_type", "unknown"),
            "court_zone": raw.get("court_zone", "unknown"),
        },
        "limitations": [
            "imported_existing_event",
            *(["pixel_not_declared"] if pixel is None else []),
        ],
    }


def import_single_rally(
    source_video: Path,
    inputs: Path,
    session_id: str,
    rally_id: str,
    profile: str,
    surface: str,
    output: Path,
    created_at: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    source_video = source_video.resolve()
    if not source_video.is_file() or source_video.suffix.lower() not in {".mp4", ".mov"}:
        raise SingleRallyError("source video must be an existing .mp4 or .mov file")
    descriptor_path = inputs.resolve()
    try:
        descriptor = load_json(descriptor_path)
        jsonschema.validate(descriptor, json.loads(INPUT_SCHEMA.read_text(encoding="utf-8")))
    except jsonschema.ValidationError as exc:
        raise SingleRallyError(f"invalid single-rally input descriptor: {exc.message}") from exc
    if (
        not isinstance(session_id, str)
        or not session_id
        or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
            for c in session_id
        )
    ):
        raise SingleRallyError("session_id contains unsafe characters")
    if (
        not isinstance(rally_id, str)
        or not rally_id
        or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
            for c in rally_id
        )
    ):
        raise SingleRallyError("rally_id contains unsafe characters")
    start = float(descriptor["start_time_seconds"])
    end = float(descriptor["end_time_seconds"])
    if not math.isfinite(start) or not math.isfinite(end) or start >= end:
        raise SingleRallyError("start_time_seconds must be less than end_time_seconds")
    files = descriptor["files"]
    base = descriptor_path.parent
    events_raw = load_events(_safe_input(base, files["events"]))
    timestamps = load_frame_timestamps(
        _safe_input(base, files["frame_timestamps"]) if files.get("frame_timestamps") else None
    )
    track = load_ball_track(_safe_input(base, files["ball_track"]), timestamps)
    if not track:
        raise SingleRallyError("ball track is empty")
    for point in track:
        if not start <= point["timestamp_seconds"] <= end:
            raise SingleRallyError("ball observation outside rally interval")
    events = [_event_record(raw, rally_id) for raw in events_raw]
    event_ids: set[str] = set()
    for event in events:
        if event["event_id"] in event_ids:
            raise SingleRallyError("duplicate event_id")
        if not start <= event["timestamp_seconds"] <= end:
            raise SingleRallyError("event timestamp outside rally interval")
        event_ids.add(event["event_id"])
    for left, right in zip(events, events[1:]):
        if (
            right["timestamp_seconds"] < left["timestamp_seconds"]
            or right["frame_id"] < left["frame_id"]
        ):
            raise SingleRallyError("events are not ordered")
    events.sort(key=lambda item: (item["timestamp_seconds"], item["frame_id"]))
    for left, right in zip(track, track[1:]):
        if (
            right["timestamp_seconds"] < left["timestamp_seconds"]
            or right["frame_id"] < left["frame_id"]
        ):
            raise SingleRallyError("ball track frames/timestamps are not ordered")
    for item in track:
        item["rally_id"] = rally_id
    court = adapt_court_map(_safe_input(base, files["court_map"]), session_id)
    limitations = list(descriptor.get("limitations", [])) + [
        "single_rally_import_read_only",
        "no_inference",
    ]
    confidence_values = [
        item["confidence"] for item in events + track if item.get("confidence") is not None
    ]
    confidence = sum(confidence_values) / len(confidence_values) if confidence_values else None
    players = {item["player"] for item in events if item["player"] in {"near", "far"}}
    rally = {
        "schema_version": "rally_record.v1",
        "rally_id": rally_id,
        "session_id": session_id,
        "index": int(descriptor.get("index", 0)),
        "start_time_seconds": start,
        "end_time_seconds": end,
        "duration_seconds": end - start,
        "source_start_frame": track[0]["frame_id"],
        "source_end_frame": track[-1]["frame_id"],
        "status": "complete",
        "event_count": len(events),
        "ball_observation_count": len(track),
        "contact_count": sum(item["event_type"] == "contact" for item in events),
        "bounce_count": sum(item["event_type"] == "bounce" for item in events),
        "player_count": len(players),
        "confidence": confidence,
        "limitations": limitations,
    }
    metrics = derive_metrics(session_id, rally_id, start, end, track, events, limitations)
    source_sha = hashlib.sha256(source_video.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="single-rally-import-") as temp_name:
        temp = Path(temp_name)
        (temp / "session.json").write_text(
            json.dumps(
                {
                    "schema_version": "session.v1",
                    "session_id": session_id,
                    "source_video": {"display_name": source_video.name, "sha256": source_sha},
                    "surface": surface,
                    "processing_profile": profile,
                    "status": "complete",
                    "capabilities": ["single_rally_import", "existing_output_transport"],
                    "limitations": limitations,
                },
                sort_keys=True,
            )
            + "\n"
        )
        (temp / "rallies.json").write_text(
            json.dumps(
                {
                    "schema_version": "rallies.v1",
                    "session_id": session_id,
                    "status": "complete",
                    "rallies": [rally],
                },
                sort_keys=True,
            )
            + "\n"
        )
        (temp / "events.jsonl").write_text(
            "\n".join(json.dumps(item, sort_keys=True) for item in events) + "\n"
        )
        (temp / "ball_track.jsonl").write_text(
            "\n".join(json.dumps(item, sort_keys=True) for item in track) + "\n"
        )
        (temp / "court_map.json").write_text(json.dumps(court, sort_keys=True) + "\n")
        (temp / "metrics.json").write_text(json.dumps(metrics, sort_keys=True) + "\n")
        descriptor_out = temp / "bundle-inputs.json"
        descriptor_out.write_text(
            json.dumps(
                {
                    "schema_version": "analysis_bundle_inputs.v1",
                    "files": {
                        name: {
                            "path": f"{name}.{'jsonl' if name in {'events', 'ball_track'} else 'json'}",
                            "required": True,
                            "media_type": "application/jsonl"
                            if name in {"events", "ball_track"}
                            else "application/json",
                            "schema_version": f"{name}.v1",
                        }
                        for name in (
                            "session",
                            "rallies",
                            "events",
                            "ball_track",
                            "court_map",
                            "metrics",
                        )
                    },
                    "capabilities": ["single_rally_import"],
                    "limitations": limitations,
                },
                sort_keys=True,
            )
            + "\n"
        )
        result = build_bundle(
            source_video,
            descriptor_out,
            session_id,
            profile,
            surface,
            output,
            created_at,
            overwrite=overwrite,
        )
    validation = validate_single_rally_bundle(output)
    report = {
        **result,
        **validation,
        "source_video": "external",
        "source_sha256": source_sha,
        "status": "imported_existing_outputs",
    }
    return report
