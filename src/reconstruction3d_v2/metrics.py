"""Physical and reprojection metrics for anchored segments."""

from __future__ import annotations

import numpy as np

from .ballistic_segments import trajectory_from_endpoints, velocity_at
from src.reconstruction3d.ballistic import net_height


def segment_metrics(camera, start, end, start_time, end_time, observations):
    duration = float(end_time - start_time)
    v0 = (
        np.asarray(end) - np.asarray(start) - 0.5 * np.array([0, 0, -9.80665]) * duration**2
    ) / duration
    errors = []
    points = []
    for obs in observations:
        p = trajectory_from_endpoints(start, end, duration, obs.timestamp_seconds - start_time)
        points.append(p)
        try:
            uv = camera.project_world_to_pixel(p)[0]
            errors.append(float(np.linalg.norm(uv - [obs.x, obs.y])))
        except ValueError:
            errors.append(float("inf"))
    grid = np.linspace(0.0, duration, 101)
    trajectory = trajectory_from_endpoints(start, end, duration, grid)
    apex_dt = min(duration, max(0.0, v0[2] / 9.80665))
    apex = trajectory_from_endpoints(start, end, duration, apex_dt)
    crossing = None
    if abs(v0[1]) > 1e-12:
        cross_dt = -float(start[1]) / float(v0[1])
        if 0 <= cross_dt <= duration:
            cross = trajectory_from_endpoints(start, end, duration, cross_dt)
            crossing = {
                "dt_seconds": cross_dt,
                "X_m": float(cross[0]),
                "Y_m": float(cross[1]),
                "Z_m": float(cross[2]),
                "net_height_m": net_height(float(cross[0])),
                "clearance_m": float(cross[2] - net_height(float(cross[0]))),
                "speed_m_s": float(np.linalg.norm(velocity_at(v0, cross_dt))),
            }
    return {
        "v0": v0,
        "v_end": velocity_at(v0, duration),
        "errors": errors,
        "trajectory": trajectory,
        "apex": apex,
        "apex_dt_seconds": apex_dt,
        "net_crossing": crossing,
        "min_z_m": float(np.min(trajectory[:, 2])),
        "max_z_m": float(np.max(trajectory[:, 2])),
    }
