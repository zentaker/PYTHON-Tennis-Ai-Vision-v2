"""Adjacent-frame player-foot tracking with RANSAC and explicit invalid states."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def _transform_points(matrix: np.ndarray, points: np.ndarray) -> np.ndarray:
    return cv2.transform(np.asarray(points, dtype=np.float32).reshape(-1, 1, 2), matrix)[:, 0]


def _bbox_corners(bbox: dict[str, float]) -> np.ndarray:
    return np.asarray(
        [
            [bbox["x1"], bbox["y1"]],
            [bbox["x2"], bbox["y1"]],
            [bbox["x2"], bbox["y2"]],
            [bbox["x1"], bbox["y2"]],
        ]
    )


def lower_body_features(gray: np.ndarray, bbox: dict[str, float], maximum: int = 60) -> np.ndarray:
    mask = np.zeros_like(gray)
    x1, x2 = int(bbox["x1"]), int(bbox["x2"])
    y1 = int(bbox["y1"] + 0.45 * (bbox["y2"] - bbox["y1"]))
    y2 = int(bbox["y2"])
    mask[max(0, y1) : min(gray.shape[0], y2), max(0, x1) : min(gray.shape[1], x2)] = 255
    points = cv2.goodFeaturesToTrack(gray, maximum, 0.01, 3, mask=mask)
    return np.empty((0, 1, 2), np.float32) if points is None else points


def track_adjacent_step(
    previous: np.ndarray,
    current: np.ndarray,
    features: np.ndarray,
    bbox: dict[str, float],
    foot_pixel: tuple[float, float],
) -> dict[str, Any]:
    """Track one adjacent pair; invalid transitions never become zero displacement."""
    if len(features) < 4:
        return {
            "valid": False,
            "tracking_state": "INVALID_INSUFFICIENT_FEATURES",
            "features": features,
        }
    forward, status, _ = cv2.calcOpticalFlowPyrLK(previous, current, features, None)
    backward, reverse, _ = cv2.calcOpticalFlowPyrLK(current, previous, forward, None)
    fb = np.linalg.norm(backward - features, axis=2)[:, 0]
    valid = status[:, 0].astype(bool) & reverse[:, 0].astype(bool) & (fb <= 1.5)
    if valid.sum() < 4:
        return {
            "valid": False,
            "tracking_state": "INVALID_FORWARD_BACKWARD",
            "features": forward[valid],
            "forward_backward_error_px": float(np.median(fb[valid])) if valid.any() else None,
        }
    old, new = features[valid, 0], forward[valid, 0]
    affine, inliers = cv2.estimateAffinePartial2D(
        old, new, method=cv2.RANSAC, ransacReprojThreshold=2.0, maxIters=500
    )
    if affine is None or inliers is None or int(inliers.sum()) < 4:
        return {"valid": False, "tracking_state": "INVALID_RANSAC", "features": forward[valid]}
    inlier_mask = inliers[:, 0].astype(bool)
    inlier_count = int(inlier_mask.sum())
    ratio = inlier_count / len(old)
    scale = float(np.hypot(affine[0, 0], affine[1, 0]))
    rotation = float(np.degrees(np.arctan2(affine[1, 0], affine[0, 0])))
    transformed_bbox = _transform_points(affine, _bbox_corners(bbox))
    new_bbox = {
        "x1": float(transformed_bbox[:, 0].min()),
        "y1": float(transformed_bbox[:, 1].min()),
        "x2": float(transformed_bbox[:, 0].max()),
        "y2": float(transformed_bbox[:, 1].max()),
    }
    foot = _transform_points(affine, np.asarray([foot_pixel]))[0]
    height, width = current.shape
    bbox_inside = (
        new_bbox["x1"] >= 0
        and new_bbox["y1"] >= 0
        and new_bbox["x2"] < width
        and new_bbox["y2"] < height
    )
    foot_inside = (
        new_bbox["x1"] <= foot[0] <= new_bbox["x2"] and new_bbox["y1"] <= foot[1] <= new_bbox["y2"]
    )
    old_crop = previous[
        max(0, int(bbox["y1"])) : min(height, int(bbox["y2"])),
        max(0, int(bbox["x1"])) : min(width, int(bbox["x2"])),
    ]
    new_crop = current[
        max(0, int(new_bbox["y1"])) : min(height, int(new_bbox["y2"])),
        max(0, int(new_bbox["x1"])) : min(width, int(new_bbox["x2"])),
    ]
    template_score = 0.0
    if old_crop.size and new_crop.size:
        normalized = cv2.resize(new_crop, (old_crop.shape[1], old_crop.shape[0]))
        template_score = float(cv2.matchTemplate(old_crop, normalized, cv2.TM_CCOEFF_NORMED)[0, 0])
    valid_state = (
        0.82 <= scale <= 1.20
        and abs(rotation) <= 15
        and bbox_inside
        and foot_inside
        and ratio >= 0.45
        and template_score >= 0.25
    )
    return {
        "valid": bool(valid_state),
        "tracking_state": "VALID" if valid_state else "INVALID_GEOMETRY_OR_APPEARANCE",
        "features": forward[valid][inlier_mask],
        "bbox": new_bbox,
        "foot_pixel": foot.tolist(),
        "feature_count": int(valid.sum()),
        "inlier_count": inlier_count,
        "inlier_ratio": ratio,
        "forward_backward_error_px": float(np.median(fb[valid])),
        "affine_scale": scale,
        "affine_rotation_deg": rotation,
        "template_score": template_score,
        "bbox_continuity": bool(0.82 <= scale <= 1.20),
        "affine": affine.tolist(),
    }


def sequential_chain(
    frames: dict[int, np.ndarray],
    contact_frame: int,
    bbox: dict[str, float],
    foot_pixel: tuple[float, float],
    direction: int,
) -> list[dict[str, Any]]:
    """Propagate contact→adjacent frames, updating reference/features/bbox/foot."""
    gray = {frame_id: cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) for frame_id, frame in frames.items()}
    current_id = contact_frame
    current_bbox = dict(bbox)
    current_foot = tuple(foot_pixel)
    features = lower_body_features(gray[current_id], current_bbox)
    output = []
    while current_id + direction in gray:
        next_id = current_id + direction
        step = track_adjacent_step(
            gray[current_id], gray[next_id], features, current_bbox, current_foot
        )
        record = {key: value for key, value in step.items() if key != "features"}
        record.update(
            {
                "frame_id": next_id,
                "reference_frame_id": current_id,
                "chain_direction": "forward" if direction > 0 else "backward",
            }
        )
        output.append(record)
        if not step["valid"]:
            break
        current_id = next_id
        current_bbox = step["bbox"]
        current_foot = tuple(step["foot_pixel"])
        features = step["features"]
        if len(features) < 8:
            features = lower_body_features(gray[current_id], current_bbox)
    return output


def valid_speed_diagnostics(
    rows: list[dict[str, Any]], timestamps: dict[int, float], xy_key: str = "ground_xy"
) -> dict[str, Any]:
    speeds, rejected = [], 0
    valid_rows = [row for row in rows if row.get("valid") and xy_key in row]
    for previous, current in zip(valid_rows, valid_rows[1:], strict=False):
        adjacent = abs(current["frame_id"] - previous["frame_id"]) == 1
        same_chain = current["chain_direction"] == previous["chain_direction"]
        dt = abs(timestamps[current["frame_id"]] - timestamps[previous["frame_id"]])
        if not adjacent or not same_chain or dt <= 0:
            rejected += 1
            continue
        speed = float(np.linalg.norm(np.asarray(current[xy_key]) - previous[xy_key]) / dt)
        if speed > 18:
            rejected += 1
            continue
        speeds.append(speed)
    return {
        "median_speed_mps": float(np.median(speeds)) if speeds else None,
        "p95_speed_mps": float(np.percentile(speeds, 95)) if speeds else None,
        "maximum_valid_speed_mps": max(speeds, default=None),
        "invalid_spike_count": rejected,
        "rejected_transitions": rejected,
        "valid_speed_samples": len(speeds),
    }
