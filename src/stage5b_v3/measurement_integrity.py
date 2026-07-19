"""Measurement-integrity audit for raw/smoothed VFR ball observations."""

from __future__ import annotations

from typing import Any

import numpy as np


def provenance_graph() -> dict[str, Any]:
    return {
        "raw": {"upstream_field": "x_raw,y_raw", "derivation": "Stage 3 detector", "independent": True, "correlation_group": "stage3_detector"},
        "smoothed": {"upstream_field": "x_smooth,y_smooth", "derivation": "Stage 3 temporal smoother", "independent": False, "correlation_group": "stage3_detector"},
        "p1_contact": {"upstream_field": "ball_pixel", "derivation": "P1 audit copied from Stage 3 observation", "independent": False, "correlation_group": "stage3_detector"},
        "interpolated": {"upstream_field": "source", "derivation": "Stage 3 interpolation", "independent": False, "correlation_group": "stage3_detector"},
        "covariance_policy": "one independent detector source receives an uncertainty floor; correlated copies are not votes",
    }


def classify_observation(row: dict[str, Any]) -> str:
    warnings = row.get("warnings", [])
    if row.get("invalid"):
        return "MEASUREMENT_INVALID"
    if "duplicate_or_frozen" in warnings:
        return "MEASUREMENT_DUPLICATE_OR_FROZEN"
    if row.get("source") == "interpolated":
        return "MEASUREMENT_INTERPOLATED"
    if row.get("confidence", 1.0) < 0.5:
        return "MEASUREMENT_LOW_CONFIDENCE"
    if "kinematically_suspicious" in warnings:
        return "MEASUREMENT_KINEMATICALLY_SUSPICIOUS"
    return "MEASUREMENT_RELIABLE"


def audit_rows(rows: list[dict[str, Any]], event_times: list[float]) -> list[dict[str, Any]]:
    rows = sorted(rows, key=lambda row: row["timestamp_seconds"])
    audited: list[dict[str, Any]] = []
    previous = None
    previous_velocity = None
    for index, row in enumerate(rows):
        raw = np.asarray(row["raw_pixel"], dtype=float)
        smooth = np.asarray(row["smoothed_pixel"], dtype=float)
        dt = None if previous is None else row["timestamp_seconds"] - previous["timestamp_seconds"]
        distance_previous = None if previous is None else float(np.linalg.norm(smooth - previous["smoothed_pixel"]))
        velocity = None if not dt or dt <= 0 else float(distance_previous / dt)
        acceleration = None if previous_velocity is None or not dt or dt <= 0 else float((velocity - previous_velocity) / dt)
        duplicate = bool(previous is not None and np.array_equal(smooth, previous["smoothed_pixel"]))
        warnings: list[str] = []
        if duplicate:
            warnings.append("duplicate_or_frozen")
        if velocity is not None and velocity > 2500:
            warnings.append("kinematically_suspicious")
        if dt is not None and dt <= 0:
            warnings.append("timestamp_invalid")
        nearest = min((abs(row["timestamp_seconds"] - value) for value in event_times), default=None)
        audited_row = {
            **row,
            "raw_pixel": raw.tolist(),
            "smoothed_pixel": smooth.tolist(),
            "pixel_velocity_px_s": velocity,
            "pixel_acceleration_px_s2": acceleration,
            "distance_to_previous_px": distance_previous,
            "distance_to_next_px": None,
            "distance_to_nearest_event_s": nearest,
            "duplicate_coordinate_run": duplicate,
            "warnings": warnings,
        }
        audited_row["measurement_status"] = classify_observation(audited_row)
        if audited:
            audited[-1]["distance_to_next_px"] = distance_previous
        audited.append(audited_row)
        previous = {"timestamp_seconds": row["timestamp_seconds"], "smoothed_pixel": smooth}
        previous_velocity = velocity
    return audited
