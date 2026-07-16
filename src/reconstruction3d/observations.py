"""Load Stage 3 observations and apply bounded, source-aware weights."""

from __future__ import annotations

import csv
from pathlib import Path

from .models import Observation


def observation_weight(source: str, confidence: float) -> float:
    """Base source weight times confidence, bounded away from zero."""
    base = {"detected": 1.0, "interpolated": 0.35}.get(source, 0.0)
    c = min(1.0, max(0.0, float(confidence)))
    return base * (0.25 + 0.75 * c) if base else 0.0


def load_trajectory(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 527 or [int(r["frame_id"]) for r in rows] != list(range(527)):
        raise ValueError("Stage 3 trajectory must contain exactly frames 0..526")
    return rows


def observations_for_range(rows: list[dict], start: int, end: int) -> list[Observation]:
    result: list[Observation] = []
    for row in rows[start : end + 1]:
        source = str(row.get("source", "missing"))
        if source not in {"detected", "interpolated"}:
            continue
        if row.get("x_smooth", "") == "" or row.get("y_smooth", "") == "":
            continue
        confidence = float(row.get("confidence", 0.0))
        result.append(
            Observation(
                int(row["frame_id"]),
                float(row["timestamp_seconds"]),
                float(row["x_smooth"]),
                float(row["y_smooth"]),
                confidence,
                source,
                observation_weight(source, confidence),
            )
        )
    return result
