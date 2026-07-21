from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from .errors import SingleRallyError


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SingleRallyError(f"input file missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SingleRallyError(f"malformed JSON input: {path}") from exc


def load_events(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        rows: list[dict[str, Any]] = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SingleRallyError(f"malformed events JSONL at line {number}") from exc
            if not isinstance(value, dict):
                raise SingleRallyError("event records must be JSON objects")
            rows.append(value)
        return rows
    payload = load_json(path)
    if isinstance(payload, dict):
        value = payload.get("narrative_events", payload.get("events"))
    else:
        value = payload
    if not isinstance(value, list):
        raise SingleRallyError("events input must contain a list")
    if not all(isinstance(item, dict) for item in value):
        raise SingleRallyError("event records must be JSON objects")
    return value


def _number(value: Any, label: str, *, allow_none: bool = False) -> float | None:
    if value is None and allow_none:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SingleRallyError(f"{label} must be numeric") from exc
    if not math.isfinite(number):
        raise SingleRallyError(f"{label} must be finite")
    return number


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise SingleRallyError(f"{label} must be an integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise SingleRallyError(f"{label} must be an integer") from exc
    if number < 0 or str(value).strip() != str(number):
        raise SingleRallyError(f"{label} must be a non-negative integer")
    return number


def load_frame_timestamps(path: Path | None) -> dict[int, float]:
    if path is None:
        return {}
    payload = load_json(path)
    frames = payload.get("frames") if isinstance(payload, dict) else payload
    if not isinstance(frames, list):
        raise SingleRallyError("frame timestamps must contain a frames list")
    output: dict[int, float] = {}
    for item in frames:
        if not isinstance(item, dict):
            raise SingleRallyError("frame timestamp records must be objects")
        frame_id = _integer(item.get("frame_id"), "frame_id")
        output[frame_id] = float(_number(item.get("timestamp_seconds"), "timestamp_seconds"))
    return output


def _track_row(row: dict[str, Any], frame_timestamps: dict[int, float]) -> dict[str, Any]:
    frame_id = _integer(row.get("frame_id"), "frame_id")
    timestamp = row.get("timestamp_seconds")
    if timestamp in (None, ""):
        if frame_id not in frame_timestamps:
            raise SingleRallyError(f"missing timestamp for frame {frame_id}")
        timestamp = frame_timestamps[frame_id]
    declared_source = str(row.get("source", "raw"))
    if "x_smooth" in row:
        x = row.get("x_smooth")
        y = row.get("y_smooth")
    else:
        x = row.get("pixel_x", row.get("x_pixel", row.get("x")))
        y = row.get("pixel_y", row.get("y_pixel", row.get("y")))
    if x in (None, "") or y in (None, ""):
        x, y = None, None
    x_value = _number(x, "pixel_x", allow_none=True)
    y_value = _number(y, "pixel_y", allow_none=True)
    confidence = _number(row.get("confidence", 0.0), "confidence")
    if confidence is None or not 0 <= confidence <= 1:
        raise SingleRallyError("confidence must be between 0 and 1")
    source = {"detected": "smoothed", "missing": "raw"}.get(declared_source, declared_source)
    if source not in {"raw", "smoothed", "interpolated"}:
        source = "raw"
    visible = row.get(
        "visible", row.get("detected_raw", x_value is not None and y_value is not None)
    )
    if isinstance(visible, str):
        visible = visible.lower() == "true"
    warnings = row.get("warnings", [])
    if not isinstance(warnings, list):
        warnings = [str(warnings)]
    if declared_source == "missing":
        warnings = [*warnings, "stage3_observation_missing"]
    if declared_source == "detected":
        warnings = [*warnings, "stage3_source_detected_mapped_to_smoothed"]
    return {
        "schema_version": "ball_track_point.v1",
        "rally_id": "",
        "frame_id": frame_id,
        "timestamp_seconds": float(_number(timestamp, "timestamp_seconds")),
        "pixel_x": x_value,
        "pixel_y": y_value,
        "confidence": confidence,
        "source": source,
        "visible": bool(visible),
        "warnings": [str(item) for item in warnings],
    }


def load_ball_track(
    path: Path, frame_timestamps: dict[int, float] | None = None
) -> list[dict[str, Any]]:
    frame_timestamps = frame_timestamps or {}
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    elif path.suffix.lower() == ".jsonl":
        rows = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SingleRallyError(f"malformed ball track JSONL at line {number}") from exc
            if not isinstance(value, dict):
                raise SingleRallyError("ball track records must be objects")
            rows.append(value)
    else:
        payload = load_json(path)
        rows = (
            payload.get("observations", payload.get("track"))
            if isinstance(payload, dict)
            else payload
        )
        if not isinstance(rows, list):
            raise SingleRallyError("ball track input must contain a list")
    output = [_track_row(row, frame_timestamps) for row in rows]
    return output


def adapt_court_map(path: Path, session_id: str) -> dict[str, Any]:
    payload = load_json(path)
    dimensions = payload.get("frame_dimensions", {})
    corners = payload.get("court_corners_pixel", {})
    width, height = dimensions.get("width"), dimensions.get("height")
    if (
        isinstance(width, bool)
        or isinstance(height, bool)
        or not isinstance(width, int)
        or not isinstance(height, int)
        or width <= 0
        or height <= 0
    ):
        raise SingleRallyError("court calibration dimensions must be positive integers")
    order = ["far_left", "far_right", "near_right", "near_left"]
    if not set(order).issubset(corners):
        raise SingleRallyError("court calibration must contain the four outer court corners")
    polygon: list[list[float]] = []
    for name in order:
        point = corners[name]
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise SingleRallyError(f"court corner {name} must contain two coordinates")
        values = [_number(value, f"court corner {name}") for value in point]
        if (
            values[0] is None
            or values[1] is None
            or not 0 <= values[0] <= width
            or not 0 <= values[1] <= height
        ):
            raise SingleRallyError(f"court corner {name} is outside image bounds")
        polygon.append([values[0], values[1]])
    homography = payload.get("H_pixel_to_court")
    if homography is not None:
        if (
            not isinstance(homography, list)
            or len(homography) != 3
            or any(not isinstance(row, list) or len(row) != 3 for row in homography)
        ):
            raise SingleRallyError("homography must be a 3x3 matrix")
        if any(_number(value, "homography value") is None for row in homography for value in row):
            raise SingleRallyError("homography must contain finite values")
    orientation = payload.get("orientation_validation", {})
    provenance = str(payload.get("provenance", "existing_court_calibration"))
    synthetic = provenance == "synthetic_contract_fixture"
    status = (
        "synthetic"
        if synthetic
        else ("approved" if orientation.get("passed") and homography is not None else "partial")
    )
    limitations = ["imported_existing_calibration", "no_3d_reconstruction"]
    if synthetic:
        limitations.append("synthetic_calibration_not_product_evidence")
    return {
        "schema_version": "court_map.v1",
        "session_id": session_id,
        "coordinate_system": "image_pixels",
        "court_coordinate_system": "court_meters",
        "image_width": width,
        "image_height": height,
        "court_polygon": polygon,
        "net_line": None,
        "homography_pixel_to_court": homography,
        "zones": {"source_layout": payload.get("layout", "unknown")},
        "provenance": provenance,
        "calibration_status": status,
        "limitations": limitations,
    }
