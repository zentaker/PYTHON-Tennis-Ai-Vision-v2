"""Independent and shared-event ballistic least-squares fitting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import least_squares

from src.geometry.camera_model import CameraModel

from .ballistic import GRAVITY_M_S2, ballistic_position, net_crossing
from .models import Observation, SegmentFit


@dataclass
class JointResult:
    event_positions: dict[str, np.ndarray]
    velocities: dict[str, np.ndarray]
    fits: list[SegmentFit]
    cost_components: dict[str, float]
    optimizer: dict[str, Any]


def _ray_at_height(camera: CameraModel, pixel: tuple[float, float], height: float) -> np.ndarray:
    origin, direction = camera.world_ray_from_pixel(*pixel)
    if abs(direction[2]) < 1e-9:
        return np.array([0.0, 0.0, height], dtype=np.float64)
    distance = (float(height) - origin[2]) / direction[2]
    if distance <= 0:
        distance = abs(distance)
    return origin + distance * direction


def _event_pixel(rows: list[dict], frame: int) -> tuple[float, float]:
    for radius in range(0, 30):
        for idx in {frame - radius, frame + radius}:
            if 0 <= idx < len(rows):
                row = rows[idx]
                if row.get("x_smooth", "") != "" and row.get("y_smooth", "") != "":
                    return float(row["x_smooth"]), float(row["y_smooth"])
    return (float(rows[frame].get("x_raw", 0.0)), float(rows[frame].get("y_raw", 0.0)))


def _initial_parameters(
    camera: CameraModel,
    rows: list[dict],
    events: list[dict],
    frame_map: dict[str, int],
    segments: list[dict],
) -> tuple[np.ndarray, dict[str, int], dict[str, int]]:
    event_index = {str(e["id"]): i for i, e in enumerate(events)}
    p_events: list[np.ndarray] = []
    for event in events:
        eid = str(event["id"])
        z = 0.0 if event["type"] == "bounce" else 1.25
        p_events.append(_ray_at_height(camera, _event_pixel(rows, frame_map[eid]), z))
        p_events[-1][2] = z
    velocities: list[np.ndarray] = []
    for segment in segments:
        a, b = event_index[str(segment["start_event"])], event_index[str(segment["end_event"])]
        ta = float(rows[frame_map[str(segment["start_event"])]]["timestamp_seconds"])
        tb = float(rows[frame_map[str(segment["end_event"])]]["timestamp_seconds"])
        dt = max(tb - ta, 1e-3)
        va = (p_events[b] - p_events[a]) / dt
        va[2] += 0.5 * GRAVITY_M_S2 * dt
        velocities.append(np.clip(va, -60.0, 60.0))
    x = np.concatenate([*p_events, *velocities]).astype(np.float64)
    return x, event_index, {str(s["segment_id"]): i for i, s in enumerate(segments)}


def _unpack(
    x: np.ndarray, n_events: int, n_segments: int
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    return [x[3 * i : 3 * i + 3] for i in range(n_events)], [
        x[3 * n_events + 3 * i : 3 * n_events + 3 * i + 3] for i in range(n_segments)
    ]


def fit_joint(
    camera: CameraModel,
    rows: list[dict],
    events: list[dict],
    segments: list[dict],
    frame_map: dict[str, int],
    observations: dict[str, list[Observation]],
    *,
    max_nfev: int = 8,
    x0: np.ndarray | None = None,
) -> JointResult:
    """Fit shared event positions and independent velocities with robust loss."""
    n_events, n_segments = len(events), len(segments)
    if x0 is None:
        x0, event_index, segment_index = _initial_parameters(
            camera, rows, events, frame_map, segments
        )
    else:
        _, event_index, segment_index = _initial_parameters(
            camera, rows, events, frame_map, segments
        )
    lower = np.full_like(x0, -90.0)
    upper = np.full_like(x0, 90.0)
    for i, event in enumerate(events):
        lower[3 * i : 3 * i + 3] = [-7.0, -40.0, 0.0]
        upper[3 * i : 3 * i + 3] = [7.0, 40.0, 4.5]
        if event["type"] == "bounce":
            # scipy requires strict bounds; this is an effectively exact Z=0
            # parametrisation (one nanometre numerical tolerance).
            lower[3 * i + 2] = 0.0
            upper[3 * i + 2] = 1e-9
    lower[3 * n_events :] = -90.0
    upper[3 * n_events :] = 90.0

    def residual(x: np.ndarray) -> np.ndarray:
        pos, vel = _unpack(x, n_events, n_segments)
        out: list[float] = []
        for si, segment in enumerate(segments):
            start = event_index[str(segment["start_event"])]
            start_time = float(rows[frame_map[str(segment["start_event"])]]["timestamp_seconds"])
            for obs in observations[str(segment["segment_id"])]:
                dt = obs.timestamp_seconds - start_time
                point = ballistic_position(pos[start], vel[si], dt)
                try:
                    projected = camera.project_world_to_pixel(point)[0]
                    if not np.all(np.isfinite(projected)):
                        raise ValueError
                    scale = max(obs.weight, 0.05)
                    out.extend(((projected - [obs.x, obs.y]) * scale).tolist())
                except (ValueError, FloatingPointError):
                    out.extend([500.0, 500.0])
            duration = (
                float(rows[frame_map[str(segment["end_event"])]]["timestamp_seconds"]) - start_time
            )
            grid = np.linspace(0.0, max(duration, 1e-4), 7)
            points = ballistic_position(pos[start], vel[si], grid)
            # Soft ground barrier: 50 px-equivalent per metre below court.
            out.extend((np.minimum(points[:, 2], 0.0) * 80.0).tolist())
            v_end_z = vel[si][2] - GRAVITY_M_S2 * duration
            if str(segment["end_type"]) == "bounce":
                out.append(max(0.0, v_end_z) * 3.0)
            if str(segment["start_type"]) == "bounce":
                out.append(max(0.0, -vel[si][2]) * 3.0)
            speed = np.linalg.norm(vel[si])
            out.append(max(0.0, speed - 90.0) * 2.0)
            crossing = net_crossing(pos[start], vel[si], duration=duration)
            if crossing is not None:
                out.append(max(0.0, -crossing["clearance_m"]) * 120.0)
        return np.asarray(out, dtype=np.float64)

    result = least_squares(
        residual,
        np.minimum(np.maximum(x0, lower + 1e-12), upper - 1e-12),
        bounds=(lower, upper),
        loss="soft_l1",
        f_scale=5.0,
        x_scale="jac",
        max_nfev=max_nfev,
        ftol=1e-9,
        xtol=1e-9,
        gtol=1e-9,
    )
    positions, velocities = _unpack(result.x, n_events, n_segments)
    fits: list[SegmentFit] = []
    reproj_values: list[float] = []
    continuity: list[float] = []
    ground_errors: list[float] = []
    net_penalty = 0.0
    for si, segment in enumerate(segments):
        sid = str(segment["segment_id"])
        start = event_index[str(segment["start_event"])]
        start_time = float(rows[frame_map[str(segment["start_event"])]]["timestamp_seconds"])
        errors: list[float] = []
        for obs in observations[sid]:
            point = ballistic_position(
                positions[start], velocities[si], obs.timestamp_seconds - start_time
            )
            try:
                errors.append(float(camera.reprojection_error(point, [[obs.x, obs.y]])[0]))
            except ValueError:
                errors.append(float("inf"))
        duration = (
            float(rows[frame_map[str(segment["end_event"])]]["timestamp_seconds"]) - start_time
        )
        sample = ballistic_position(positions[start], velocities[si], np.linspace(0, duration, 31))
        ground_errors.append(float(max(0.0, -np.min(sample[:, 2]))))
        crossing = net_crossing(positions[start], velocities[si], duration=duration)
        if crossing is not None:
            net_penalty += max(0.0, -crossing["clearance_m"])
        status = (
            "FIT_ACCEPTED"
            if errors and np.nanpercentile(errors, 95) <= 25 and np.max(sample[:, 2]) < 4.5
            else "FIT_MARGINAL"
        )
        if not errors:
            status = "FIT_REJECTED"
        fits.append(
            SegmentFit(
                sid,
                str(segment["start_event"]),
                str(segment["end_event"]),
                frame_map[str(segment["start_event"])],
                frame_map[str(segment["end_event"])],
                np.r_[positions[start], velocities[si]],
                status=status,
                observations_used=len(errors),
                metrics={
                    "reprojection_mean_px": float(np.mean(errors)) if errors else None,
                    "reprojection_median_px": float(np.median(errors)) if errors else None,
                    "reprojection_p95_px": float(np.percentile(errors, 95)) if errors else None,
                    "reprojection_max_px": float(np.max(errors)) if errors else None,
                    "min_z_m": float(np.min(sample[:, 2])),
                    "max_z_m": float(np.max(sample[:, 2])),
                    "duration_seconds": duration,
                    "net_crossing": crossing,
                },
            )
        )
        reproj_values.extend(errors)
        continuity.append(
            float(
                np.linalg.norm(
                    ballistic_position(positions[start], velocities[si], duration)
                    - positions[event_index[str(segment["end_event"])]]
                )
            )
        )
    components = {
        "reprojection": float(np.mean(np.square(reproj_values))) if reproj_values else float("inf"),
        "continuity": float(max(continuity, default=0.0)),
        "ground": float(max(ground_errors, default=0.0)),
        "net_clearance_penalty": float(net_penalty),
        "regularization": 0.0,
    }
    return JointResult(
        {str(e["id"]): positions[i] for i, e in enumerate(events)},
        {str(s["segment_id"]): velocities[i] for i, s in enumerate(segments)},
        fits,
        components,
        {
            "success": bool(result.success),
            "message": result.message,
            "nfev": int(result.nfev),
            "cost": float(result.cost),
            "optimality": float(result.optimality),
        },
    )
