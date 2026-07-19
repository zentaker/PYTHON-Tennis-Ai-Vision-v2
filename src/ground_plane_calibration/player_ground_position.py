"""Uncertain player foot-pixel estimation and ground-method fusion."""

from __future__ import annotations

from typing import Any

import numpy as np

FOOT_NAMES = (
    "left_ankle", "left_heel", "left_big_toe", "left_small_toe",
    "right_ankle", "right_heel", "right_big_toe", "right_small_toe",
)


def estimate_foot_pixel(
    keypoints: list[dict[str, Any]], bbox: dict[str, float], neighbors: list[tuple[float, float]] | None = None
) -> dict[str, Any]:
    """Estimate a support foot using visibility, confidence, vertical rank and time."""
    usable = [
        point for point in keypoints
        if point.get("name") in FOOT_NAMES and point.get("visible", True)
        and float(point.get("confidence", 0.0)) >= 0.25
    ]
    warnings: list[str] = []
    fallback = len(usable) < 2
    if fallback:
        pixel = np.array([(float(bbox["x1"]) + float(bbox["x2"])) / 2, float(bbox["y2"])])
        uncertainty = max(6.0, 0.08 * (float(bbox["y2"]) - float(bbox["y1"])))
        warnings.append("BBOX_BOTTOM_FALLBACK")
    else:
        coordinates = np.array([[point["x"], point["y"]] for point in usable], dtype=float)
        confidence = np.array([point["confidence"] for point in usable], dtype=float)
        vertical = coordinates[:, 1]
        support = vertical >= np.percentile(vertical, 45)
        weights = confidence[support] * (1.0 + (vertical[support] - vertical.min()) / max(1.0, np.ptp(vertical)))
        pixel = np.average(coordinates[support], axis=0, weights=weights)
        uncertainty = max(2.0, float(np.sqrt(np.mean(np.sum((coordinates[support] - pixel) ** 2, axis=1)))))
        if float(np.ptp(vertical)) > 0.2 * (float(bbox["y2"]) - float(bbox["y1"])):
            warnings.append("ELEVATED_OR_ASYMMETRIC_FOOT")
        if float(np.ptp(coordinates[:, 0])) > 0.45 * (float(bbox["x2"]) - float(bbox["x1"])):
            warnings.append("EXCESSIVE_FOOT_SPREAD")
    if neighbors:
        neighbor = np.median(np.asarray(neighbors, dtype=float), axis=0)
        if np.linalg.norm(neighbor - pixel) <= max(20.0, 2.5 * uncertainty):
            pixel = 0.7 * pixel + 0.3 * neighbor
        else:
            warnings.append("TEMPORAL_SUPPORT_DISAGREES")
    return {
        "pixel": [float(pixel[0]), float(pixel[1])],
        "pixel_uncertainty": float(uncertainty),
        "supporting_keypoints": [point["name"] for point in usable],
        "temporal_support": len(neighbors or []),
        "fallback_used": fallback,
        "warnings": warnings,
    }


def fuse_ground_estimates(
    homography_xy: tuple[float, float], camera_xy: tuple[float, float],
    homography_uncertainty: float, camera_uncertainty: float, threshold_m: float = 1.0,
) -> dict[str, Any]:
    homography = np.asarray(homography_xy, dtype=float)
    camera = np.asarray(camera_xy, dtype=float)
    disagreement = float(np.linalg.norm(homography - camera))
    if not np.isfinite(disagreement) or disagreement > threshold_m:
        return {
            "resolved": False, "fused_xy": None, "method_disagreement_m": disagreement,
            "metric_uncertainty_m": max(homography_uncertainty, camera_uncertainty, disagreement),
            "warnings": ["GROUND_METHOD_DISAGREEMENT"],
        }
    weights = 1.0 / np.square([homography_uncertainty, camera_uncertainty])
    fused = np.average(np.vstack([homography, camera]), axis=0, weights=weights)
    return {
        "resolved": True, "fused_xy": [float(fused[0]), float(fused[1])],
        "method_disagreement_m": disagreement,
        "metric_uncertainty_m": float(np.sqrt(1.0 / weights.sum())), "warnings": [],
    }
