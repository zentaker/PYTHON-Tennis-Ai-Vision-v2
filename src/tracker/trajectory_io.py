"""CSV IO helpers for Stage 3 trajectory data."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable


RAW_COLUMNS = ["frame_id", "x_pixel", "y_pixel", "confidence"]
SMOOTHED_COLUMNS = [
    "frame_id",
    "x_raw",
    "y_raw",
    "confidence",
    "x_smooth",
    "y_smooth",
    "source",
    "is_outlier",
    "reason",
]


def _parse_optional_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _format_optional_float(value: float | None, digits: int = 3) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}"


def read_wasb_detections(path: Path) -> list[dict]:
    """Read the Stage 2 WASB CSV into plain dictionaries."""
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in RAW_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Missing required columns in {path}: {missing}")
        rows = []
        for row in reader:
            rows.append(
                {
                    "frame_id": int(row["frame_id"]),
                    "x_raw": _parse_optional_float(row["x_pixel"]),
                    "y_raw": _parse_optional_float(row["y_pixel"]),
                    "confidence": float(row["confidence"]),
                }
            )
    return rows


def write_smoothed_trajectory(path: Path, rows: Iterable[dict]) -> None:
    """Write Stage 3 smoothed trajectory rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SMOOTHED_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "frame_id": row["frame_id"],
                    "x_raw": _format_optional_float(row.get("x_raw")),
                    "y_raw": _format_optional_float(row.get("y_raw")),
                    "confidence": f"{row['confidence']:.6f}",
                    "x_smooth": _format_optional_float(row.get("x_smooth")),
                    "y_smooth": _format_optional_float(row.get("y_smooth")),
                    "source": row["source"],
                    "is_outlier": str(bool(row["is_outlier"])).lower(),
                    "reason": row["reason"],
                }
            )
