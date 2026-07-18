"""Deterministic kinematic estimators using real, potentially VFR timestamps."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .contracts import BallKinematics, BallTrajectorySample

MPS_TO_KMH = 3.6


def estimate_speed(
    samples: Sequence[BallTrajectorySample],
    method: str,
    *,
    max_gap_seconds: float = 0.5,
    outlier_mad_scale: float = 6.0,
) -> BallKinematics:
    """Estimate median segment speed after strict validation and robust rejection."""
    if method not in {"pixel_apparent", "court_planar_xy", "estimated_3d"}:
        raise ValueError(f"unsupported method: {method}")
    speed_unit = "pixels_per_second" if method == "pixel_apparent" else "metres_per_second"
    warnings: list[str] = []
    if len(samples) < 2:
        return _unavailable(method, speed_unit, len(samples), "at least two samples required")
    data = np.asarray(
        [[sample.timestamp_seconds, sample.x, sample.y, np.nan if sample.z is None else sample.z]
         for sample in samples],
        dtype=float,
    )
    if not np.isfinite(data[:, :3]).all():
        return _unavailable(method, speed_unit, 0, "non-finite timestamp or coordinate")
    dt = np.diff(data[:, 0])
    if np.any(dt <= 0):
        return _unavailable(method, speed_unit, 0, "timestamps must be strictly increasing")
    if method == "estimated_3d" and not np.isfinite(data[:, 3]).all():
        return _unavailable(method, speed_unit, 0, "approved Z evidence is required")
    expected_unit = "pixels" if method == "pixel_apparent" else "metres"
    if any(sample.coordinate_unit != expected_unit for sample in samples):
        return _unavailable(method, speed_unit, 0, f"coordinates must use {expected_unit}")
    dims = data[:, 1:3] if method != "estimated_3d" else data[:, 1:4]
    segment_speed = np.linalg.norm(np.diff(dims, axis=0), axis=1) / dt
    keep = np.isfinite(segment_speed) & (dt <= max_gap_seconds)
    rejected = int((~keep).sum())
    if np.any(dt > max_gap_seconds):
        warnings.append("segments crossing timestamp gaps were rejected")
    candidates = segment_speed[keep]
    if candidates.size >= 3:
        ordered = np.sort(candidates)
        adjacent_gaps = np.diff(ordered)
        split_at = int(np.argmax(adjacent_gaps)) if adjacent_gaps.size else 0
        lower = ordered[: split_at + 1]
        upper = ordered[split_at + 1 :]
        clear_split = (
            upper.size > 0
            and adjacent_gaps[split_at] > max(1e-9, 3.0 * float(np.median(lower)))
        )
        if clear_split:
            selected = lower if lower.size >= upper.size else upper
            rejected += int(candidates.size - selected.size)
            candidates = selected
            warnings.append("kinematic outlier cluster was rejected")
        median = float(np.median(candidates))
        mad = float(np.median(np.abs(candidates - median)))
        if mad > 0:
            robust_keep = np.abs(candidates - median) <= outlier_mad_scale * mad
        else:
            robust_keep = np.isclose(candidates, median)
        rejected += int((~robust_keep).sum())
        candidates = candidates[robust_keep]
        if not robust_keep.all():
            warnings.append("kinematic outliers were rejected with a MAD filter")
    if candidates.size == 0:
        return _unavailable(method, speed_unit, rejected, "no valid speed segments")
    speed = float(np.median(candidates))
    confidence = min(1.0, candidates.size / 4.0)
    if len(samples) == 2:
        warnings.append("estimate uses only two samples; a larger window is preferred")
    if method == "pixel_apparent":
        warnings.append("apparent pixel speed is diagnostic only")
        outgoing_mps = outgoing_kmh = None
    else:
        outgoing_mps, outgoing_kmh = speed, speed * MPS_TO_KMH
        if method == "court_planar_xy":
            warnings.append("planar XY speed ignores Z and is not real 3D speed")
    return BallKinematics(
        status="available",
        method=method,
        speed_unit=speed_unit,
        outgoing_speed_mps=outgoing_mps,
        outgoing_speed_kmh=outgoing_kmh,
        peak_outgoing_speed_kmh=(float(np.max(candidates)) * MPS_TO_KMH
                                 if method != "pixel_apparent" else None),
        samples_used=int(candidates.size + 1),
        rejected_samples=rejected,
        window_start_seconds=float(data[0, 0]),
        window_end_seconds=float(data[-1, 0]),
        confidence=confidence,
        warnings=tuple(warnings),
    )


def _unavailable(method: str, unit: str, rejected: int, warning: str) -> BallKinematics:
    return BallKinematics(
        status="unavailable",
        method=method,
        speed_unit=unit,
        rejected_samples=rejected,
        confidence=0.0,
        warnings=(warning,),
    )
