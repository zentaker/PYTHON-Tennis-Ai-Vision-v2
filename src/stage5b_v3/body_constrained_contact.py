"""Conservative body-linked wrist/contact candidates with separated uncertainty and reach."""

from __future__ import annotations

from typing import Any

import numpy as np

from .contact_ray_feasibility import point_on_ray_at_height


def _kp(pose: dict[str, Any], name: str) -> dict[str, Any] | None:
    return next((row for row in pose["keypoints"] if row["name"] == name), None)


def body_contact_candidates(
    camera,
    pose: dict[str, Any],
    anchor: dict[str, Any],
    ball_pixel: tuple[float, float],
    *,
    racket_length_m: float = 0.75,
) -> dict[str, Any]:
    ground = np.asarray([anchor["fused_x_m"], anchor["fused_y_m"], 0.0])
    ci95 = np.asarray(anchor["total_ci95"], dtype=float)
    shoulders = [_kp(pose, name) for name in ("left_shoulder", "right_shoulder")]
    hips = [_kp(pose, name) for name in ("left_hip", "right_hip")]
    wrists = {name: _kp(pose, name) for name in ("left_wrist", "right_wrist")}
    candidates = []
    for hand, wrist in wrists.items():
        if wrist is None or not wrist.get("visible"):
            continue
        for contact_height in np.linspace(0.7, 3.0, 20):
            ball, lambda_ball = point_on_ray_at_height(camera, ball_pixel, float(contact_height))
            wrist_point, lambda_wrist = point_on_ray_at_height(
                camera, (wrist["x"], wrist["y"]), float(min(2.8, contact_height))
            )
            shoulder_conf = np.mean([row["confidence"] for row in shoulders if row])
            hip_conf = np.mean([row["confidence"] for row in hips if row])
            body_reach = float(np.linalg.norm(wrist_point - ground))
            anchor_sigma = np.maximum((ci95[1] - ci95[0]) / 3.92, 0.15)
            anchor_mahal = float(np.linalg.norm((wrist_point[:2] - ground[:2]) / anchor_sigma))
            wrist_residual = float(
                np.linalg.norm(
                    camera.project_world_to_pixel(wrist_point)[0]
                    - np.asarray([wrist["x"], wrist["y"]])
                )
            )
            anatomical_cost = (
                abs(body_reach - 1.5) / 1.5
                + max(0.0, 0.2 - shoulder_conf)
                + max(0.0, 0.2 - hip_conf)
            )
            racket_residual = max(0.0, float(np.linalg.norm(ball - wrist_point)) - racket_length_m)
            candidates.append(
                {
                    "event_frame": pose["frame_id"],
                    "timestamp": pose["timestamp_seconds"],
                    "ball_pixel": list(ball_pixel),
                    "ball_ray_parameter": lambda_ball,
                    "xyz": ball.tolist(),
                    "selected_hand": hand,
                    "wrist_xyz": wrist_point.tolist(),
                    "ground_anchor_xyz": ground.tolist(),
                    "shoulder_xyz": None,
                    "player_ground_xy": ground[:2].tolist(),
                    "contact_height_m": float(contact_height),
                    "racket_length_m": racket_length_m,
                    "anatomical_cost": anatomical_cost,
                    "anchor_mahalanobis_cost": anchor_mahal,
                    "ball_pixel_cost": 0.0,
                    "wrist_pixel_cost": wrist_residual,
                    "timing_cost": 0.0,
                    "confidence": float(pose.get("confidence", 0.0)),
                    "racket_residual_m": racket_residual,
                    "prior_log_probability": -anatomical_cost - anchor_mahal - racket_residual,
                }
            )
    candidates.sort(key=lambda row: row["prior_log_probability"], reverse=True)
    best = candidates[:8]
    return {
        "method_status": "BODY_CONTACT_APPROXIMATE",
        "method_scope": "ground_anchor_ball_ray_wrist_ray_reach_only",
        "body_3d_reconstructed": False,
        "candidates": best,
        "support_probability": float(
            sum(row["racket_residual_m"] <= 0.25 for row in candidates) / max(1, len(candidates))
        ),
        "feasible_sample_fraction": float(
            sum(row["racket_residual_m"] <= 0.25 for row in candidates) / max(1, len(candidates))
        ),
        "anchor_likelihood": float(np.exp(-best[0]["anchor_mahalanobis_cost"])) if best else 0.0,
        "anatomical_residual": best[0]["anatomical_cost"] if best else None,
        "wrist_reprojection_residual": best[0]["wrist_pixel_cost"] if best else None,
        "racket_residual": best[0]["racket_residual_m"] if best else None,
        "total_likelihood": float(np.exp(best[0]["prior_log_probability"])) if best else 0.0,
    }
