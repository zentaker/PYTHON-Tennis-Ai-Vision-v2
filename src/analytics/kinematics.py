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
        outgoing_status="available",
        outgoing_speed_mps=outgoing_mps,
        outgoing_speed_kmh=outgoing_kmh,
        peak_outgoing_speed_kmh=(float(np.max(candidates)) * MPS_TO_KMH
                                 if method != "pixel_apparent" else None),
        samples_used=int(candidates.size + 1),
        rejected_samples=rejected,
        window_start_seconds=float(data[0, 0]),
        window_end_seconds=float(data[-1, 0]),
        confidence=confidence,
        outgoing_confidence=confidence,
        warnings=tuple(warnings),
    )


def estimate_event_kinematics(
    samples: Sequence[BallTrajectorySample],
    contact_timestamp_seconds: float,
    method: str,
    *,
    pre_window_seconds: float = 0.5,
    post_window_seconds: float = 0.5,
    max_gap_seconds: float = 0.5,
    outlier_mad_scale: float = 6.0,
) -> BallKinematics:
    """Estimate independent incoming and outgoing speeds around one contact."""
    if not np.isfinite(contact_timestamp_seconds):
        return _unavailable(method, _speed_unit(method), 0, "contact timestamp must be finite")
    if pre_window_seconds <= 0 or post_window_seconds <= 0:
        raise ValueError("contact windows must be positive")
    ordered = list(samples)
    incoming = [
        sample
        for sample in ordered
        if contact_timestamp_seconds - pre_window_seconds
        <= sample.timestamp_seconds
        <= contact_timestamp_seconds
    ]
    outgoing = [
        sample
        for sample in ordered
        if contact_timestamp_seconds
        <= sample.timestamp_seconds
        <= contact_timestamp_seconds + post_window_seconds
    ]
    common = {
        "max_gap_seconds": max_gap_seconds,
        "outlier_mad_scale": outlier_mad_scale,
    }
    incoming_result = estimate_speed(incoming, method, **common)
    outgoing_result = estimate_speed(outgoing, method, **common)
    incoming_available = incoming_result.status == "available"
    outgoing_available = outgoing_result.status == "available"
    if incoming_available and outgoing_available:
        status = "available"
    elif incoming_available or outgoing_available:
        status = "partial"
    else:
        status = "unavailable"
    warnings = tuple(f"incoming: {warning}" for warning in incoming_result.warnings) + tuple(
        f"outgoing: {warning}" for warning in outgoing_result.warnings
    )
    confidences = [
        value
        for value, available in (
            (incoming_result.confidence, incoming_available),
            (outgoing_result.confidence, outgoing_available),
        )
        if available
    ]
    return BallKinematics(
        status=status,
        method=method,
        speed_unit=_speed_unit(method),
        incoming_status="available" if incoming_available else "unavailable",
        outgoing_status="available" if outgoing_available else "unavailable",
        incoming_speed_mps=(incoming_result.outgoing_speed_mps if incoming_available else None),
        incoming_speed_kmh=(incoming_result.outgoing_speed_kmh if incoming_available else None),
        outgoing_speed_mps=(outgoing_result.outgoing_speed_mps if outgoing_available else None),
        outgoing_speed_kmh=(outgoing_result.outgoing_speed_kmh if outgoing_available else None),
        peak_outgoing_speed_kmh=(
            outgoing_result.peak_outgoing_speed_kmh if outgoing_available else None
        ),
        samples_used=incoming_result.samples_used + outgoing_result.samples_used,
        rejected_samples=(
            incoming_result.rejected_samples + outgoing_result.rejected_samples
        ),
        incoming_samples_used=incoming_result.samples_used,
        incoming_rejected_samples=incoming_result.rejected_samples,
        outgoing_samples_used=outgoing_result.samples_used,
        outgoing_rejected_samples=outgoing_result.rejected_samples,
        window_start_seconds=(
            incoming_result.window_start_seconds if incoming_available else None
        ),
        window_end_seconds=(outgoing_result.window_end_seconds if outgoing_available else None),
        confidence=min(confidences) if confidences else 0.0,
        incoming_confidence=incoming_result.confidence if incoming_available else 0.0,
        outgoing_confidence=outgoing_result.confidence if outgoing_available else 0.0,
        warnings=warnings,
    )


def _speed_unit(method: str) -> str:
    if method == "pixel_apparent":
        return "pixels_per_second"
    if method in {"court_planar_xy", "estimated_3d"}:
        return "metres_per_second"
    raise ValueError(f"unsupported method: {method}")


def _unavailable(method: str, unit: str, rejected: int, warning: str) -> BallKinematics:
    return BallKinematics(
        status="unavailable",
        method=method,
        speed_unit=unit,
        rejected_samples=rejected,
        confidence=0.0,
        warnings=(warning,),
    )
