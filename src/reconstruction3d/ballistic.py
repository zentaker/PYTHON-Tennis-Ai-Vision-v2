"""Gravity-only trajectories and physical diagnostics."""

from __future__ import annotations

from typing import Any

import numpy as np

GRAVITY_M_S2 = 9.80665


def ballistic_position(p0: Any, v0: Any, dt: Any, gravity: float = GRAVITY_M_S2) -> np.ndarray:
    """Return ``P0 + V0*t + (0,0,-g*t²/2)`` in float64."""
    p = np.asarray(p0, dtype=np.float64)
    v = np.asarray(v0, dtype=np.float64)
    t = np.asarray(dt, dtype=np.float64)
    if p.shape != (3,) or v.shape != (3,) or not np.all(np.isfinite([*p, *v])):
        raise ValueError("p0 and v0 must be finite vectors of length three")
    if not np.all(np.isfinite(t)):
        raise ValueError("dt must be finite")
    result = np.asarray(p + t[..., None] * v, dtype=np.float64)
    result[..., 2] -= 0.5 * float(gravity) * t * t
    return result


def ballistic_velocity(v0: Any, dt: Any, gravity: float = GRAVITY_M_S2) -> np.ndarray:
    v = np.asarray(v0, dtype=np.float64)
    t = np.asarray(dt, dtype=np.float64)
    result = np.broadcast_to(v, t[..., None].shape[:-1] + (3,)).copy() if t.ndim else v.copy()
    result = np.asarray(v + t[..., None] * np.array([0.0, 0.0, -float(gravity)]), dtype=np.float64)
    return result


def apex_time(p0: Any, v0: Any, gravity: float = GRAVITY_M_S2) -> float:
    del p0
    vz = float(np.asarray(v0, dtype=np.float64)[2])
    return max(0.0, vz / float(gravity))


def net_height(
    x: float,
    *,
    half_width_m: float = 5.485,
    center_height_m: float = 0.914,
    post_height_m: float = 1.07,
) -> float:
    """Linear regulation-net approximation, documented for diagnostics."""
    ratio = min(1.0, abs(float(x)) / half_width_m)
    return float(center_height_m + ratio * (post_height_m - center_height_m))


def net_crossing(
    p0: Any, v0: Any, *, duration: float, gravity: float = GRAVITY_M_S2
) -> dict[str, float] | None:
    p = np.asarray(p0, dtype=np.float64)
    v = np.asarray(v0, dtype=np.float64)
    if abs(v[1]) < 1e-12:
        return None
    t = -p[1] / v[1]
    if t < 0 or t > duration:
        return None
    point = ballistic_position(p, v, t, gravity)
    height = net_height(float(point[0]))
    return {
        "dt_seconds": float(t),
        "X_m": float(point[0]),
        "Y_m": float(point[1]),
        "Z_m": float(point[2]),
        "net_height_m": height,
        "clearance_m": float(point[2] - height),
        "speed_m_s": float(np.linalg.norm(ballistic_velocity(v, t, gravity))),
    }
