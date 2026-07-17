"""Endpoint-determined ballistic segments with exact spatial continuity."""

from __future__ import annotations

import numpy as np

GRAVITY = np.array([0.0, 0.0, -9.80665], dtype=np.float64)


def endpoint_velocity(start: np.ndarray, end: np.ndarray, duration_seconds: float) -> np.ndarray:
    if duration_seconds <= 0:
        raise ValueError("duration must be positive")
    return (
        np.asarray(end, dtype=np.float64)
        - np.asarray(start, dtype=np.float64)
        - 0.5 * GRAVITY * duration_seconds**2
    ) / duration_seconds


def trajectory_from_endpoints(
    start: np.ndarray, end: np.ndarray, duration_seconds: float, dt: float | np.ndarray
) -> np.ndarray:
    start = np.asarray(start, dtype=np.float64)
    velocity = endpoint_velocity(start, np.asarray(end, dtype=np.float64), duration_seconds)
    t = np.asarray(dt, dtype=np.float64)
    return start + t[..., None] * velocity + 0.5 * t[..., None] ** 2 * GRAVITY


def velocity_at(v0: np.ndarray, dt: float | np.ndarray) -> np.ndarray:
    return np.asarray(v0, dtype=np.float64) + np.asarray(dt)[..., None] * GRAVITY
