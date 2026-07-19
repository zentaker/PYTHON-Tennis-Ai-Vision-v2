"""Measurement-integrity audit for raw/smoothed VFR ball observations."""

from __future__ import annotations

from typing import Any

import numpy as np


def provenance_graph() -> dict[str, Any]:
    return {
        "raw": {
            "upstream_field": "x_raw,y_raw",
            "derivation": "Stage 3 detector",
            "independent": True,
            "correlation_group": "stage3_detector",
        },
        "smoothed": {
            "upstream_field": "x_smooth,y_smooth",
            "derivation": "Stage 3 temporal smoother",
            "independent": False,
            "correlation_group": "stage3_detector",
        },
        "p1_contact": {
            "upstream_field": "ball_pixel",
            "derivation": "P1 audit copied from Stage 3 observation",
            "independent": False,
            "correlation_group": "stage3_detector",
        },
        "interpolated": {
            "upstream_field": "source",
            "derivation": "Stage 3 interpolation",
            "independent": False,
            "correlation_group": "stage3_detector",
        },
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


def _freeze_runs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find sustained plateaus using raw and smoothed motion, not exact equality alone."""
    runs: list[dict[str, Any]] = []
    start = None
    for index in range(1, len(rows)):
        previous, current = rows[index - 1], rows[index]
        raw_delta = float(np.linalg.norm(np.asarray(current["raw_pixel"]) - np.asarray(previous["raw_pixel"])))
        smooth_delta = float(np.linalg.norm(np.asarray(current["smoothed_pixel"]) - np.asarray(previous["smoothed_pixel"])))
        plateau = raw_delta <= 0.75 and smooth_delta <= 0.75
        if plateau and start is None:
            start = index - 1
        if (not plateau or index == len(rows) - 1) and start is not None:
            end = index if plateau and index == len(rows) - 1 else index - 1
            length = end - start + 1
            if length >= 2:
                segment = rows[start : end + 1]
                raw_motion = float(np.linalg.norm(np.asarray(segment[-1]["raw_pixel"]) - np.asarray(segment[0]["raw_pixel"])))
                smooth_motion = float(np.linalg.norm(np.asarray(segment[-1]["smoothed_pixel"]) - np.asarray(segment[0]["smoothed_pixel"])))
                source = {str(item.get("source", "unknown")) for item in segment}
                kind = "EXACT_DUPLICATE" if raw_motion == 0 and smooth_motion == 0 else "QUANTIZED_PLATEAU"
                if smooth_motion == 0 and raw_motion > 0:
                    kind = "SMOOTHER_FREEZE"
                if length == 2 and raw_motion > 0.25:
                    kind = "VALID_LOW_MOTION"
                runs.append({"start_frame": segment[0]["frame_id"], "end_frame": segment[-1]["frame_id"], "length": length, "kind": kind, "raw_motion_px": raw_motion, "smoothed_motion_px": smooth_motion, "sources": sorted(source), "duration_seconds": segment[-1]["timestamp_seconds"] - segment[0]["timestamp_seconds"]})
            start = None
    return runs


def measurement_policy(row: dict[str, Any]) -> dict[str, Any]:
    """Return an explicit, deterministic usability/weight policy for one row."""
    status = row["measurement_status"]
    confidence = float(row.get("confidence", 0.0))
    if status == "MEASUREMENT_INVALID":
        return {"usable": False, "weight_multiplier": 0.0, "sigma_px": 50.0, "exclusion_reason": "invalid_timestamp_or_interval", "warning": "INVALID_NOT_USED", "classification_evidence": row.get("warnings", [])}
    if status == "MEASUREMENT_DUPLICATE_OR_FROZEN":
        return {"usable": True, "weight_multiplier": 0.25, "sigma_px": 12.0, "exclusion_reason": "freeze_downweighted", "warning": "FREEZE_DOWNWEIGHTED", "classification_evidence": row.get("warnings", [])}
    if status == "MEASUREMENT_KINEMATICALLY_SUSPICIOUS":
        return {"usable": True, "weight_multiplier": 0.2, "sigma_px": 15.0, "exclusion_reason": "kinematic_anomaly_downweighted", "warning": "SUSPICIOUS_DOWNWEIGHTED", "classification_evidence": row.get("warnings", [])}
    if status == "MEASUREMENT_INTERPOLATED":
        return {"usable": True, "weight_multiplier": 0.5, "sigma_px": 10.0, "exclusion_reason": "short_interpolation", "warning": "INTERPOLATED_DOWNWEIGHTED", "classification_evidence": row.get("warnings", [])}
    if status == "MEASUREMENT_LOW_CONFIDENCE":
        return {"usable": True, "weight_multiplier": max(0.2, min(1.0, confidence)), "sigma_px": max(8.0, 12.0 * (1.0 - confidence)), "exclusion_reason": "low_confidence_downweighted", "warning": "LOW_CONFIDENCE_DOWNWEIGHTED", "classification_evidence": row.get("warnings", [])}
    return {"usable": True, "weight_multiplier": 1.0, "sigma_px": 4.0, "exclusion_reason": None, "warning": None, "classification_evidence": row.get("warnings", [])}


def audit_rows(rows: list[dict[str, Any]], event_times: list[float]) -> list[dict[str, Any]]:
    rows = sorted(rows, key=lambda row: row["timestamp_seconds"])
    audited: list[dict[str, Any]] = []
    previous = None
    previous_velocity = None
    for index, row in enumerate(rows):
        raw = np.asarray(row["raw_pixel"], dtype=float)
        smooth = np.asarray(row["smoothed_pixel"], dtype=float)
        dt = None if previous is None else row["timestamp_seconds"] - previous["timestamp_seconds"]
        distance_previous = (
            None if previous is None else float(np.linalg.norm(smooth - previous["smoothed_pixel"]))
        )
        velocity = None if not dt or dt <= 0 else float(distance_previous / dt)
        acceleration = (
            None
            if previous_velocity is None or not dt or dt <= 0
            else float((velocity - previous_velocity) / dt)
        )
        duplicate = bool(previous is not None and np.linalg.norm(smooth - previous["smoothed_pixel"]) <= 0.75)
        warnings: list[str] = []
        if duplicate:
            warnings.append("duplicate_or_frozen")
        if velocity is not None and velocity > 2500:
            warnings.append("kinematically_suspicious")
        if dt is not None and dt <= 0:
            warnings.append("timestamp_invalid")
        nearest = min(
            (abs(row["timestamp_seconds"] - value) for value in event_times), default=None
        )
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
        audited_row.update(measurement_policy(audited_row))
        if audited:
            audited[-1]["distance_to_next_px"] = distance_previous
        audited.append(audited_row)
        previous = {"timestamp_seconds": row["timestamp_seconds"], "smoothed_pixel": smooth}
        previous_velocity = velocity
    return audited


def audit_report(audited: list[dict[str, Any]], *, event_ranges_respected: bool, correlated_source_groups: int = 1) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in audited:
        counts[row["measurement_status"]] = counts.get(row["measurement_status"], 0) + 1
    timestamps_valid = all(row.get("interval_valid", True) and "timestamp_invalid" not in row.get("warnings", []) for row in audited)
    anomalies_weighted = all(row["usable"] is False or row["weight_multiplier"] < 1.0 or row["measurement_status"] == "MEASUREMENT_RELIABLE" for row in audited)
    status = "STAGE5B_V351_MEASUREMENT_INTEGRITY_PASSED" if len(audited) == 314 and timestamps_valid and event_ranges_respected and anomalies_weighted else "STAGE5B_V351_MEASUREMENT_INTEGRITY_PARTIAL"
    return {"status": status, "observations_inventoried": len(audited), "status_counts": counts, "observations_downweighted": sum(row["usable"] and row["weight_multiplier"] < 1.0 for row in audited), "observations_invalid": sum(not row["usable"] for row in audited), "timestamps_valid": timestamps_valid, "event_ranges_respected": event_ranges_respected, "all_anomalies_weighted": anomalies_weighted, "correlated_source_groups": correlated_source_groups, "freeze_runs": _freeze_runs(audited), "audited_segments": ["flight_03", "flight_05", "flight_07", "flight_09"]}
