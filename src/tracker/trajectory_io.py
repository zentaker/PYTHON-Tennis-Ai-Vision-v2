"""Validated CSV IO helpers for legacy and VFR-aware Stage 3 trajectories."""

from __future__ import annotations

import csv
import math
from collections.abc import Iterable
from pathlib import Path


RAW_COLUMNS = ["frame_id", "x_pixel", "y_pixel", "confidence"]
OPTIONAL_RAW_COLUMNS = [
    "timestamp_seconds",
    "detected",
    "canonical_width",
    "canonical_height",
]
SMOOTHED_COLUMNS = [
    "frame_id",
    "timestamp_seconds",
    "x_raw",
    "y_raw",
    "confidence",
    "detected_raw",
    "x_smooth",
    "y_smooth",
    "source",
    "is_outlier",
    "reason",
    "canonical_width",
    "canonical_height",
]


def _parse_optional_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Expected a finite number, found {value!r}")
    return number


def _parse_optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    number = int(value)
    if number <= 0:
        raise ValueError("Canonical dimensions must be positive")
    return number


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None or value == "":
        return default
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise ValueError(f"Expected true/false, found {value!r}")
    return normalized == "true"


def _format_optional_float(value: float | None, digits: int = 9) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}"


def _validate_rows(rows: list[dict], path: Path) -> None:
    if not rows:
        raise ValueError(f"Detection CSV is empty: {path}")
    expected_ids = list(range(len(rows)))
    frame_ids = [row["frame_id"] for row in rows]
    if frame_ids != expected_ids:
        raise ValueError("frame_id values must be consecutive and start at 0")

    timestamp_presence = [row["timestamp_seconds"] is not None for row in rows]
    if any(timestamp_presence) and not all(timestamp_presence):
        raise ValueError("timestamp_seconds must be present for every row or none")
    if all(timestamp_presence):
        timestamps = [float(row["timestamp_seconds"]) for row in rows]
        if any(current <= previous for previous, current in zip(timestamps, timestamps[1:])):
            raise ValueError("timestamp_seconds values must be strictly increasing")

    dimensions = {
        (row["canonical_width"], row["canonical_height"])
        for row in rows
        if row["canonical_width"] is not None or row["canonical_height"] is not None
    }
    if any(None in pair for pair in dimensions):
        raise ValueError("canonical_width and canonical_height must appear together")
    if len(dimensions) > 1:
        raise ValueError("Canonical dimensions must be constant across the CSV")

    for row in rows:
        confidence = float(row["confidence"])
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError(f"Invalid confidence at frame {row['frame_id']}")
        width = row["canonical_width"]
        height = row["canonical_height"]
        if row["detected_raw"] and width is not None:
            x_value = row["x_raw"]
            y_value = row["y_raw"]
            if x_value is None or y_value is None:
                raise ValueError(f"Detected frame {row['frame_id']} has no coordinates")
            if not (0 <= x_value < width and 0 <= y_value < height):
                raise ValueError(f"Detected frame {row['frame_id']} is outside canonical bounds")


def read_wasb_detections(path: Path) -> list[dict]:
    """Read legacy four-column or orientation-aware Stage 2 WASB detections."""
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing = [column for column in RAW_COLUMNS if column not in fieldnames]
        if missing:
            raise ValueError(f"Missing required columns in {path}: {missing}")
        rows: list[dict] = []
        for row in reader:
            x_raw = _parse_optional_float(row.get("x_pixel"))
            y_raw = _parse_optional_float(row.get("y_pixel"))
            has_xy = x_raw is not None and y_raw is not None
            rows.append(
                {
                    "frame_id": int(row["frame_id"]),
                    "timestamp_seconds": _parse_optional_float(row.get("timestamp_seconds")),
                    "x_raw": x_raw,
                    "y_raw": y_raw,
                    "confidence": float(row["confidence"]),
                    "detected_raw": _parse_bool(row.get("detected"), default=has_xy),
                    "canonical_width": _parse_optional_int(row.get("canonical_width")),
                    "canonical_height": _parse_optional_int(row.get("canonical_height")),
                }
            )
    _validate_rows(rows, path)
    return rows


def write_smoothed_trajectory(path: Path, rows: Iterable[dict]) -> None:
    """Write Stage 3 rows while retaining optional legacy metadata as empty fields."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SMOOTHED_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "frame_id": row["frame_id"],
                    "timestamp_seconds": _format_optional_float(row.get("timestamp_seconds")),
                    "x_raw": _format_optional_float(row.get("x_raw"), digits=3),
                    "y_raw": _format_optional_float(row.get("y_raw"), digits=3),
                    "confidence": f"{row['confidence']:.6f}",
                    "detected_raw": str(bool(row.get("detected_raw", True))).lower(),
                    "x_smooth": _format_optional_float(row.get("x_smooth"), digits=3),
                    "y_smooth": _format_optional_float(row.get("y_smooth"), digits=3),
                    "source": row["source"],
                    "is_outlier": str(bool(row["is_outlier"])).lower(),
                    "reason": row["reason"],
                    "canonical_width": row.get("canonical_width") or "",
                    "canonical_height": row.get("canonical_height") or "",
                }
            )
