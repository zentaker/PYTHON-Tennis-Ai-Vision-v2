from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from ..analysis_bundle.validator import validate_bundle
from .errors import SingleRallyError

ROOT = Path(__file__).parents[3]
SCHEMAS = {
    "rally": ROOT / "config/product/rally_record_v1.schema.json",
    "event": ROOT / "config/product/event_v1.schema.json",
    "track": ROOT / "config/product/ball_track_point_v1.schema.json",
    "court": ROOT / "config/product/court_map_v1.schema.json",
    "metrics": ROOT / "config/product/metrics_v1.schema.json",
}


def _check(value: Any, name: str) -> None:
    try:
        jsonschema.validate(value, json.loads(SCHEMAS[name].read_text(encoding="utf-8")))
    except jsonschema.ValidationError as exc:
        raise SingleRallyError(f"{name} schema invalid: {exc.message}") from exc


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SingleRallyError(f"malformed {path.name} at line {number}") from exc
        if not isinstance(value, dict):
            raise SingleRallyError(f"{path.name} records must be objects")
        rows.append(value)
    return rows


def validate_single_rally_bundle(bundle: Path) -> dict[str, Any]:
    base = validate_bundle(bundle)
    try:
        rallies = json.loads((bundle / "rallies.json").read_text(encoding="utf-8"))
        metrics = json.loads((bundle / "metrics.json").read_text(encoding="utf-8"))
        court = json.loads((bundle / "court_map.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SingleRallyError("canonical rally JSON files are unreadable") from exc
    events = _read_jsonl(bundle / "events.jsonl")
    track = _read_jsonl(bundle / "ball_track.jsonl")
    records = rallies.get("rallies") if isinstance(rallies, dict) else None
    if not isinstance(records, list) or len(records) != 1:
        raise SingleRallyError("Stage 1A requires exactly one rally record")
    rally = records[0]
    _check(rally, "rally")
    for event in events:
        _check(event, "event")
    for point in track:
        _check(point, "track")
    _check(court, "court")
    _check(metrics, "metrics")
    session_id = base["session_id"]
    rally_id = rally["rally_id"]
    if rally["session_id"] != session_id or rallies.get("session_id") != session_id:
        raise SingleRallyError("rally/session session_id mismatch")
    if metrics["session_id"] != session_id or metrics["rally_id"] != rally_id:
        raise SingleRallyError("metrics session_id or rally_id mismatch")
    if court["session_id"] != session_id:
        raise SingleRallyError("court_map session_id mismatch")
    if rally["index"] != 0 or rally["start_time_seconds"] >= rally["end_time_seconds"]:
        raise SingleRallyError("rally interval is invalid")
    start, end = rally["start_time_seconds"], rally["end_time_seconds"]
    previous_time = -1.0
    previous_frame = -1
    event_ids: set[str] = set()
    for event in events:
        if event["rally_id"] != rally_id:
            raise SingleRallyError("event rally_id mismatch")
        if event["event_id"] in event_ids:
            raise SingleRallyError("duplicate event_id")
        if not start <= event["timestamp_seconds"] <= end:
            raise SingleRallyError("event timestamp outside rally interval")
        if event["timestamp_seconds"] < previous_time or event["frame_id"] < previous_frame:
            raise SingleRallyError("events are not ordered")
        event_ids.add(event["event_id"])
        previous_time, previous_frame = event["timestamp_seconds"], event["frame_id"]
    previous_time = -1.0
    previous_frame = -1
    for point in track:
        if point["rally_id"] != rally_id:
            raise SingleRallyError("ball track rally_id mismatch")
        if not start <= point["timestamp_seconds"] <= end:
            raise SingleRallyError("ball observation outside rally interval")
        if point["timestamp_seconds"] < previous_time or point["frame_id"] < previous_frame:
            raise SingleRallyError("ball track is not ordered")
        previous_time, previous_frame = point["timestamp_seconds"], point["frame_id"]
    contacts = sum(item["event_type"] == "contact" for item in events)
    bounces = sum(item["event_type"] == "bounce" for item in events)
    if rally["event_count"] != len(events) or rally["ball_observation_count"] != len(track):
        raise SingleRallyError("rally declared counts do not match written records")
    if rally["contact_count"] != contacts or rally["bounce_count"] != bounces:
        raise SingleRallyError("rally contact/bounce counts do not match events")
    if metrics["ball_observations"] != len(track) or metrics["contacts"] != contacts:
        raise SingleRallyError("metrics counts do not match written records")
    if metrics["bounces"] != bounces:
        raise SingleRallyError("metrics bounce count does not match events")
    return {**base, "rally_id": rally_id, "events": len(events), "ball_observations": len(track)}
