"""Court model, line sampling, and robust homography refinement."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from scipy.optimize import least_squares

COURT_LINES = {
    "left_doubles": ((-5.485, -11.885), (-5.485, 11.885)),
    "right_doubles": ((5.485, -11.885), (5.485, 11.885)),
    "left_singles": ((-4.115, -11.885), (-4.115, 11.885)),
    "right_singles": ((4.115, -11.885), (4.115, 11.885)),
    "near_baseline": ((-5.485, -11.885), (5.485, -11.885)),
    "far_baseline": ((-5.485, 11.885), (5.485, 11.885)),
    "near_service": ((-4.115, -6.4), (4.115, -6.4)),
    "far_service": ((-4.115, 6.4), (4.115, 6.4)),
    "net": ((-5.485, 0.0), (5.485, 0.0)),
    "center_service": ((0.0, -6.4), (0.0, 6.4)),
}


@dataclass(frozen=True, slots=True)
class RefinementResult:
    homography: np.ndarray
    initial_errors: np.ndarray
    refined_errors: np.ndarray
    condition: float
    infinity_line: tuple[float, float, float]


def apply_homography(matrix: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Project N two-dimensional points through a homography."""
    points = np.asarray(points, dtype=float)
    homogeneous = np.column_stack([points, np.ones(len(points))]) @ matrix.T
    return homogeneous[:, :2] / homogeneous[:, 2:3]


def sample_court_lines(samples: int = 60) -> tuple[np.ndarray, np.ndarray]:
    points, identifiers = [], []
    for name, (start, end) in COURT_LINES.items():
        line = np.linspace(start, end, samples)
        points.extend(line)
        identifiers.extend([name] * samples)
    return np.asarray(points), np.asarray(identifiers)


def line_distance_errors(h_court_to_pixel: np.ndarray, distance: np.ndarray) -> np.ndarray:
    points, _ = sample_court_lines()
    pixels = apply_homography(h_court_to_pixel, points)
    x = np.clip(np.rint(pixels[:, 0]).astype(int), 0, distance.shape[1] - 1)
    y = np.clip(np.rint(pixels[:, 1]).astype(int), 0, distance.shape[0] - 1)
    outside = (
        (pixels[:, 0] < 0)
        | (pixels[:, 0] >= distance.shape[1])
        | (pixels[:, 1] < 0)
        | (pixels[:, 1] >= distance.shape[0])
    )
    values = distance[y, x].astype(float)
    values[outside] = 50.0
    return values


def refine_homography(
    initial: np.ndarray,
    distance: np.ndarray,
    court_points: np.ndarray,
    pixel_points: np.ndarray,
    regularization: float = 0.08,
) -> RefinementResult:
    """Refine court-to-pixel H against line distance with correspondence prior."""
    initial = np.asarray(initial, dtype=float) / float(initial[2, 2])
    initial_parameters = initial.ravel()[:8]

    def matrix(parameters: np.ndarray) -> np.ndarray:
        return np.append(parameters, 1.0).reshape(3, 3)

    def residual(parameters: np.ndarray) -> np.ndarray:
        candidate = matrix(parameters)
        line = line_distance_errors(candidate, distance)
        prior = (apply_homography(candidate, court_points) - pixel_points).ravel()
        scale = np.maximum(1.0, np.abs(initial_parameters))
        reg = (parameters - initial_parameters) / scale
        return np.concatenate([line, 0.35 * prior, regularization * reg])

    fit = least_squares(residual, initial_parameters, loss="soft_l1", max_nfev=120)
    refined = matrix(fit.x)
    return RefinementResult(
        refined,
        line_distance_errors(initial, distance),
        line_distance_errors(refined, distance),
        float(np.linalg.cond(refined)),
        tuple(float(value) for value in np.linalg.inv(refined).T[2]),
    )


def synthetic_line_mask(h_court_to_pixel: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Render the regulation court model for deterministic tests."""
    mask = np.zeros(shape, dtype=np.uint8)
    for start, end in COURT_LINES.values():
        pixels = apply_homography(h_court_to_pixel, np.asarray([start, end]))
        cv2.line(mask, tuple(np.rint(pixels[0]).astype(int)), tuple(np.rint(pixels[1]).astype(int)), 255, 2)
    return mask
