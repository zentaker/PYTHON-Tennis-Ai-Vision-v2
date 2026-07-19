"""Ray-constrained contact existence solver from primary camera and pose evidence."""

from __future__ import annotations

from typing import Any

import numpy as np

from src.geometry.camera_model import CameraModel


def point_on_ray_at_height(
    camera: CameraModel, pixel: tuple[float, float], height_m: float
) -> tuple[np.ndarray, float]:
    origin, direction = camera.world_ray_from_pixel(*pixel)
    if abs(direction[2]) < 1e-12:
        raise ValueError("ray parallel to requested height plane")
    ray_parameter = (height_m - origin[2]) / direction[2]
    if ray_parameter <= 0:
        raise ValueError("point is behind camera")
    point = origin + ray_parameter * direction
    return point, float(ray_parameter)


def round_trip_error(camera: CameraModel, pixel: tuple[float, float], height_m: float) -> float:
    point, _ = point_on_ray_at_height(camera, pixel, height_m)
    projected = camera.project_world_to_pixel(point)[0]
    return float(np.linalg.norm(projected - pixel))


def solve_contact_ray(
    camera: CameraModel,
    ball_pixel: tuple[float, float],
    wrist_pixels: dict[str, tuple[float, float]],
    anchor: dict[str, Any],
    *,
    racket_length_m: float = 0.75,
    arm_allowance_m: float = 0.55,
    height_range_m: tuple[float, float] = (0.45, 3.25),
    samples: int = 80,
    ball_pixel_covariance: list[list[float]] | None = None,
) -> dict[str, Any]:
    ci95 = np.asarray(anchor["total_ci95"], dtype=float)
    ground_center = np.asarray([anchor["fused_x_m"], anchor["fused_y_m"]])
    anchor_radius = float(np.linalg.norm((ci95[1] - ci95[0]) / 2))
    pixel_allowance_m = 0.0
    if ball_pixel_covariance is not None:
        pixel_sigma = float(np.sqrt(np.max(np.linalg.eigvalsh(ball_pixel_covariance))))
        pixel_allowance_m = min(0.5, pixel_sigma * 0.02)
    candidates: list[dict[str, Any]] = []
    by_hand: dict[str, list[dict[str, Any]]] = {}
    for hand, wrist_pixel in wrist_pixels.items():
        hand_candidates = []
        for height in np.linspace(*height_range_m, samples):
            ball_point, lambda_ball = point_on_ray_at_height(camera, ball_pixel, float(height))
            wrist_heights = np.linspace(max(0.55, height - 1.1), min(2.8, height + 1.1), 50)
            best = None
            for wrist_height in wrist_heights:
                wrist_point, lambda_wrist = point_on_ray_at_height(
                    camera, wrist_pixel, float(wrist_height)
                )
                racket_distance = float(np.linalg.norm(ball_point - wrist_point))
                horizontal_reach = float(np.linalg.norm(ball_point[:2] - ground_center))
                geometric_excess = max(0.0, racket_distance - racket_length_m) + max(
                    0.0, horizontal_reach - anchor_radius - racket_length_m - arm_allowance_m
                )
                geometric_excess = max(0.0, geometric_excess - pixel_allowance_m)
                row = {
                    "hand": hand,
                    "ball_point_3d": ball_point.tolist(),
                    "wrist_point_3d": wrist_point.tolist(),
                    "lambda_ball": lambda_ball,
                    "lambda_wrist": lambda_wrist,
                    "contact_height_m": float(height),
                    "wrist_height_m": float(wrist_height),
                    "effective_racket_length_m": racket_length_m,
                    "wrist_to_ball_m": racket_distance,
                    "horizontal_reach_m": horizontal_reach,
                    "geometric_excess_m": geometric_excess,
                }
                if best is None or row["geometric_excess_m"] < best["geometric_excess_m"]:
                    best = row
            if best and best["geometric_excess_m"] <= 0.25:
                hand_candidates.append(best)
        by_hand[hand] = hand_candidates
        candidates.extend(hand_candidates)
    feasible_hands = [hand for hand, rows in by_hand.items() if rows]
    if not feasible_hands:
        status = "CONTACT_RAY_INFEASIBLE"
        best_candidate = None
    else:
        status = "CONTACT_RAY_AMBIGUOUS" if len(feasible_hands) > 1 else "CONTACT_RAY_FEASIBLE"
        best_candidate = min(candidates, key=lambda row: row["geometric_excess_m"])
    intervals = {
        hand: [min(row["lambda_ball"] for row in rows), max(row["lambda_ball"] for row in rows)]
        for hand, rows in by_hand.items()
        if rows
    }
    return {
        "event_id": anchor.get("event_id"),
        "status": status,
        "ball_ray": {
            "origin": camera.world_ray_from_pixel(*ball_pixel)[0].tolist(),
            "direction": camera.world_ray_from_pixel(*ball_pixel)[1].tolist(),
            "pixel": list(ball_pixel),
        },
        "wrist_rays": {
            hand: {
                "origin": camera.world_ray_from_pixel(*pixel)[0].tolist(),
                "direction": camera.world_ray_from_pixel(*pixel)[1].tolist(),
                "pixel": list(pixel),
            }
            for hand, pixel in wrist_pixels.items()
        },
        "player_ground_anchor_distribution": {
            "mean_xy": ground_center.tolist(),
            "total_ci95": anchor["total_ci95"],
        },
        "feasible_ball_ray_intervals": intervals,
        "feasible_wrist_candidates": feasible_hands,
        "candidate_3d_contact_points": candidates,
        "best_candidate": best_candidate,
        "alternative_candidates": sorted(candidates, key=lambda row: row["geometric_excess_m"])[
            1:6
        ],
        "geometric_residual_m": best_candidate["geometric_excess_m"] if best_candidate else None,
        "uncertainty": {
            "ball_pixel_covariance": ball_pixel_covariance,
            "ball_pixel_allowance_m": pixel_allowance_m,
            "anchor": "total_ci95",
            "wrist_px": 6.0,
        },
        "hand_ambiguity": len(feasible_hands) > 1,
        "round_trip_error_px": round_trip_error(camera, ball_pixel, 1.5),
    }
