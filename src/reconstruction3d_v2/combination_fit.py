"""Real five-height optimisation for every event-frame combination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import least_squares

from .anchored_events import event_point, side_pass
from .metrics import segment_metrics
from src.reconstruction3d.observations import observations_for_range


@dataclass
class AnchoredFit:
    frame_map: dict[str, int]
    heights: dict[str, float]
    events: dict[str, np.ndarray]
    segments: list[dict[str, Any]]
    cost: float
    convergence: bool
    nfev: int
    status: str
    rejection_reason: str
    physical_checks: dict[str, Any]
    semantic_checks: dict[str, Any]


def _event_pixel(rows, frame, event, observations_cache):
    from .event_observations import observe_event

    observation = observe_event(rows, event, frame)
    if not observation.valid:
        raise ValueError(observation.reason)
    observations_cache[str(event["id"])] = observation
    return observation.pixel_x, observation.pixel_y


def fit_combination(
    camera, rows, events, segments, frame_map, semantic_constraints=None, starts=16
) -> AnchoredFit:
    event_obs = {}
    pixels = {}
    try:
        for event in events:
            pixels[str(event["id"])] = _event_pixel(
                rows, frame_map[str(event["id"])], event, event_obs
            )
    except ValueError as exc:
        return AnchoredFit(
            frame_map, {}, {}, [], float("inf"), False, 0, "REJECTED", str(exc), {}, {}
        )
    height_events = [e for e in events if e["type"] != "bounce"]
    names = [str(e["id"]) for e in height_events]
    lower = np.array(
        [0.5 if e["type"] == "serve" else 0.1 for e in height_events], dtype=np.float64
    )
    upper = np.full(len(names), 4.5, dtype=np.float64)
    # The human semantic constraint bounds ev_003 only by the ray-derived Y,
    # never by an invented physical height.
    for i, event in enumerate(height_events):
        if event["id"] == "ev_003":
            origin, direction = camera.world_ray_from_pixel(*pixels["ev_003"])
            upper[i] = min(
                upper[i],
                float(origin[2] + (11.885 - origin[1]) * direction[2] / direction[1])
                if abs(direction[1]) > 1e-12
                else 4.5,
            )
            upper[i] = max(lower[i] + 1e-5, upper[i] - 1e-5)

    def build(values):
        points = {}
        for event in events:
            eid = str(event["id"])
            if event["type"] == "bounce":
                points[eid] = event_point(camera, event, pixels[eid], 0.0)
            else:
                points[eid] = event_point(
                    camera, event, pixels[eid], float(values[names.index(eid)])
                )
        return points

    obs_by_segment = {}
    for segment in segments:
        obs_by_segment[str(segment["segment_id"])] = observations_for_range(
            rows, frame_map[str(segment["start_event"])], frame_map[str(segment["end_event"])]
        )

    def evaluate(values):
        points = build(values)
        residual = []
        for segment in segments:
            sid = str(segment["segment_id"])
            start_id = str(segment["start_event"])
            end_id = str(segment["end_event"])
            start_t = float(rows[frame_map[start_id]]["timestamp_seconds"])
            end_t = float(rows[frame_map[end_id]]["timestamp_seconds"])
            start, end = points[start_id], points[end_id]
            duration = end_t - start_t
            for obs in obs_by_segment[sid]:
                p = (
                    start
                    + (obs.timestamp_seconds - start_t)
                    * ((end - start - 0.5 * np.array([0, 0, -9.80665]) * duration**2) / duration)
                    + 0.5 * (obs.timestamp_seconds - start_t) ** 2 * np.array([0, 0, -9.80665])
                )
                try:
                    projected = camera.project_world_to_pixel(p)[0]
                    residual.extend(((projected - [obs.x, obs.y]) * max(obs.weight, 0.05)).tolist())
                except ValueError:
                    residual.extend([500.0, 500.0])
            # Penalties only for physical violations; endpoint continuity is exact.
            grid = np.linspace(0, duration, 25)
            traj = (
                start
                + grid[:, None]
                * ((end - start - 0.5 * np.array([0, 0, -9.80665]) * duration**2) / duration)
                + 0.5 * grid[:, None] ** 2 * np.array([0, 0, -9.80665])
            )
            residual.extend((np.minimum(traj[:, 2], 0.0) * 100.0).tolist())
            v0 = (end - start - 0.5 * np.array([0, 0, -9.80665]) * duration**2) / duration
            residual.append(max(0.0, np.linalg.norm(v0) - 90.0) * 2.0)
        return np.asarray(residual, dtype=np.float64)

    rng = np.random.default_rng(20260716)
    initial = [np.clip((lower + upper) / 2, lower, upper)]
    initial.extend(rng.uniform(lower, upper) for _ in range(max(0, starts - 1)))
    best = None
    for x0 in initial:
        result = least_squares(
            evaluate,
            x0,
            bounds=(lower, upper),
            loss="soft_l1",
            f_scale=5.0,
            max_nfev=800,
            ftol=1e-10,
            xtol=1e-10,
            gtol=1e-10,
        )
        if best is None or result.cost < best.cost:
            best = result
    assert best is not None
    points = build(best.x)
    semantic = {}
    for event in events:
        passed, reason = side_pass(event, points[str(event["id"])])
        if event["id"] == "ev_003":
            passed = passed and points["ev_003"][1] > 11.885
            reason = "behind_far_baseline" if passed else "ev_003_not_behind_far_baseline"
        semantic[str(event["id"])] = {
            "pass": bool(passed),
            "reason": reason,
            "Y_m": float(points[str(event["id"])][1]),
        }
    fit_segments = []
    min_z = 0.0
    max_error = 0.0
    clearances = []
    for segment in segments:
        sid = str(segment["segment_id"])
        start_id = str(segment["start_event"])
        end_id = str(segment["end_event"])
        metrics = segment_metrics(
            camera,
            points[start_id],
            points[end_id],
            float(rows[frame_map[start_id]]["timestamp_seconds"]),
            float(rows[frame_map[end_id]]["timestamp_seconds"]),
            obs_by_segment[sid],
        )
        errors = metrics["errors"]
        min_z = min(min_z, metrics["min_z_m"])
        max_error = max(max_error, max(errors, default=0.0))
        if metrics["net_crossing"]:
            clearances.append(metrics["net_crossing"]["clearance_m"])
        fit_segments.append(
            {
                "segment_id": sid,
                "start_event": start_id,
                "end_event": end_id,
                "start_frame": frame_map[start_id],
                "end_frame": frame_map[end_id],
                "start_point_m": points[start_id].tolist(),
                "end_point_m": points[end_id].tolist(),
                "duration_seconds": float(rows[frame_map[end_id]]["timestamp_seconds"])
                - float(rows[frame_map[start_id]]["timestamp_seconds"]),
                "v0_m_s": metrics["v0"].tolist(),
                "v_end_m_s": metrics["v_end"].tolist(),
                "metrics": {
                    "reprojection_mean_px": float(np.mean(errors)) if errors else None,
                    "reprojection_median_px": float(np.median(errors)) if errors else None,
                    "reprojection_p95_px": float(np.percentile(errors, 95)) if errors else None,
                    "reprojection_max_px": float(max(errors, default=0.0)),
                    "apex_height_m": float(metrics["apex"][2]),
                    "apex_dt_seconds": metrics["apex_dt_seconds"],
                    "min_z_m": metrics["min_z_m"],
                    "max_z_m": metrics["max_z_m"],
                    "net_crossing": metrics["net_crossing"],
                    "observations_used": len(errors),
                    "coverage": len(errors) / max(1, frame_map[end_id] - frame_map[start_id] + 1),
                },
            }
        )
    physical = {
        "endpoints_exact": True,
        "bounce_z_exact": bool(
            all(abs(points[str(e["id"])][2]) <= 1e-8 for e in events if e["type"] == "bounce")
        ),
        "min_z_m": float(min_z),
        "max_speed_m_s": float(
            max(float(np.linalg.norm(np.asarray(s["v0_m_s"]))) for s in fit_segments)
        ),
        "max_reprojection_px": float(max_error),
        "net_clearance_nonnegative": bool(min(clearances, default=0.0) >= 0.0),
    }
    valid = (
        all(item["pass"] for item in semantic.values())
        and physical["min_z_m"] >= -0.02
        and physical["max_speed_m_s"] <= 90
    )
    status = (
        "ANCHORED_FIT_REJECTED"
        if not valid
        else (
            "ANCHORED_FIT_ACCEPTED"
            if all(
                (s["metrics"]["reprojection_median_px"] or 1e9) <= 10
                and (s["metrics"]["reprojection_p95_px"] or 1e9) <= 25
                for s in fit_segments
            )
            else "ANCHORED_FIT_MARGINAL"
        )
    )
    return AnchoredFit(
        frame_map,
        {name: float(value) for name, value in zip(names, best.x, strict=True)},
        points,
        fit_segments,
        float(best.cost),
        bool(best.success),
        int(best.nfev),
        status,
        "" if valid else "semantic_or_physical_constraint_failed",
        physical,
        semantic,
    )
