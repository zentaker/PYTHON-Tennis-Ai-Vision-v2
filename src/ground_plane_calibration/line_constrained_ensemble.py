"""Robust homography fitting driven by classified painted-line segments."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.optimize import least_squares

from .court_line_refinement import COURT_LINES, apply_homography

LONGITUDINAL = {"left_doubles", "right_doubles", "left_singles", "right_singles", "center_service"}
TRANSVERSE = {"near_baseline", "far_baseline", "near_service", "far_service"}


def _line_distance(points: np.ndarray, line: np.ndarray) -> np.ndarray:
    vector = line[1] - line[0]
    return np.abs(np.cross(vector, points - line[0]) / np.linalg.norm(vector))


def identifiable(segments: list[dict[str, Any]]) -> bool:
    families = {row["line_family_candidate"] for row in segments if row.get("accepted", True)}
    return bool(families & LONGITUDINAL and families & TRANSVERSE and len(families) >= 3)


def fit_line_constrained_homography(
    initial: np.ndarray,
    segments: list[dict[str, Any]],
    court_points: np.ndarray,
    corner_pixels: np.ndarray,
) -> dict[str, Any]:
    """Fit H using actual segment endpoints/midpoints/orientations and corner priors."""
    accepted = [row for row in segments if row.get("accepted", True)]
    if not identifiable(accepted):
        raise ValueError("insufficient longitudinal/transverse line geometry")
    initial = np.asarray(initial, dtype=float) / initial[2, 2]
    base = initial.ravel()[:8]

    def matrix(parameters: np.ndarray) -> np.ndarray:
        return np.append(parameters, 1.0).reshape(3, 3)

    def residual(parameters: np.ndarray) -> np.ndarray:
        candidate = matrix(parameters)
        values: list[float] = []
        for row in accepted:
            family = row["line_family_candidate"]
            model = apply_homography(candidate, np.asarray(COURT_LINES[family]))
            endpoints = np.asarray(row["endpoints"], dtype=float)
            midpoint = endpoints.mean(axis=0, keepdims=True)
            weight = np.sqrt(max(1.0, float(row["length_px"])) / 100.0)
            values.extend((_line_distance(endpoints, model) * weight).tolist())
            values.extend((_line_distance(midpoint, model) * weight).tolist())
            model_angle = np.arctan2(*(model[1] - model[0])[::-1])
            observed_angle = np.radians(float(row["orientation_deg"]))
            values.append(float(np.sin(model_angle - observed_angle) * 8.0 * weight))
        corner_prior = (apply_homography(candidate, court_points) - corner_pixels).ravel() * 0.35
        regularization = (parameters - base) / np.maximum(1.0, np.abs(base)) * 0.1
        condition_penalty = [max(0.0, np.log10(np.linalg.cond(candidate)) - 5.0)]
        return np.concatenate([np.asarray(values), corner_prior, regularization, condition_penalty])

    fit = least_squares(residual, base, loss="soft_l1", max_nfev=180)
    result = matrix(fit.x)
    line_errors = []
    for row in accepted:
        model = apply_homography(result, np.asarray(COURT_LINES[row["line_family_candidate"]]))
        line_errors.extend(_line_distance(np.asarray(row["endpoints"]), model).tolist())
    return {
        "H_court_to_pixel": result.tolist(),
        "segments_used": len(accepted),
        "model_line_families": sorted({row["line_family_candidate"] for row in accepted}),
        "line_median_px": float(np.median(line_errors)),
        "line_p95_px": float(np.percentile(line_errors, 95)),
        "corner_residual_px": float(
            np.median(
                np.linalg.norm(apply_homography(result, court_points) - corner_pixels, axis=1)
            )
        ),
        "condition": float(np.linalg.cond(result)),
        "line_at_infinity": np.linalg.inv(result).T[2].tolist(),
        "optimization_cost": float(fit.cost),
        "optimizer_nfev": int(fit.nfev),
        "accepted": bool(fit.success and np.isfinite(result).all()),
        "acceptance_reason": "IDENTIFIABLE_ROBUST_LINE_AND_CORNER_FIT"
        if fit.success
        else "OPTIMIZER_FAILED",
    }


def real_family_subsets(segments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    accepted = [row for row in segments if row.get("accepted", True)]
    families = {
        "all_accepted_painted_segments": accepted,
        "longitudinal_plus_baselines": [
            row
            for row in accepted
            if row["line_family_candidate"] in LONGITUDINAL | {"near_baseline", "far_baseline"}
        ],
        "baselines_plus_sidelines": [
            row
            for row in accepted
            if row["line_family_candidate"]
            in {
                "near_baseline",
                "far_baseline",
                "left_doubles",
                "right_doubles",
                "left_singles",
                "right_singles",
            }
        ],
        "interior_service_plus_sidelines": [
            row
            for row in accepted
            if row["line_family_candidate"]
            in {"near_service", "far_service", "center_service", "left_singles", "right_singles"}
        ],
    }
    for omitted in sorted({row["line_family_candidate"] for row in accepted}):
        families[f"leave_{omitted}_out"] = [
            row for row in accepted if row["line_family_candidate"] != omitted
        ]
    for modulo in (2, 3):
        families[f"deterministic_subset_mod{modulo}"] = [
            row for index, row in enumerate(accepted) if index % modulo != 0
        ]
    return families


RADIAL_DISTORTION_STATUS = "RADIAL_DISTORTION_NOT_IDENTIFIABLE_FROM_CURRENT_INPUTS"
