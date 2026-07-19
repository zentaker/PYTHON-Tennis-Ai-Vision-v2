"""Real-image line support and CPU temporal foot validation primitives."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

PAINTED_LINE_NAMES = (
    "left_doubles",
    "right_doubles",
    "left_singles",
    "right_singles",
    "near_baseline",
    "far_baseline",
    "near_service",
    "far_service",
    "center_service",
)


def segment_orientation(segment: np.ndarray) -> float:
    delta = segment[1] - segment[0]
    return float(np.degrees(np.arctan2(delta[1], delta[0])) % 180.0)


def detect_line_segments(
    gray: np.ndarray, ground_mask: np.ndarray, min_length: float = 35.0
) -> list[dict[str, Any]]:
    """Detect real LSD segments whose midpoint lies on the visible-ground mask."""
    detector = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
    detected = detector.detect(gray)[0]
    results = []
    if detected is None:
        return results
    for raw in detected[:, 0]:
        start, end = raw[:2], raw[2:]
        length = float(np.linalg.norm(end - start))
        midpoint = np.rint((start + end) / 2).astype(int)
        inside = 0 <= midpoint[1] < gray.shape[0] and 0 <= midpoint[0] < gray.shape[1]
        if length < min_length or not inside or ground_mask[midpoint[1], midpoint[0]] == 0:
            continue
        results.append(
            {
                "endpoints": [start.tolist(), end.tolist()],
                "length_px": length,
                "orientation_deg": segment_orientation(np.asarray([start, end])),
            }
        )
    return sorted(results, key=lambda row: (-row["length_px"], row["endpoints"]))


def classify_segments(
    segments: list[dict[str, Any]],
    projected_lines: dict[str, np.ndarray],
    distance_gate_px: float = 18.0,
    angle_gate_deg: float = 14.0,
) -> list[dict[str, Any]]:
    """Associate detected image segments to the closest painted model line."""
    output = []
    for row in segments:
        endpoints = np.asarray(row["endpoints"], dtype=float)
        midpoint = endpoints.mean(axis=0)
        best = (float("inf"), None, float("inf"))
        for name, line in projected_lines.items():
            if name not in PAINTED_LINE_NAMES:
                continue
            vector = line[1] - line[0]
            denominator = float(np.dot(vector, vector))
            fraction = float(np.clip(np.dot(midpoint - line[0], vector) / denominator, 0, 1))
            distance = float(np.linalg.norm(midpoint - (line[0] + fraction * vector)))
            angle = abs(row["orientation_deg"] - segment_orientation(line))
            angle = min(angle, 180 - angle)
            score = distance + angle
            if score < best[0]:
                best = (score, name, distance, angle)
        _, family, residual, angle = best
        accepted = residual <= distance_gate_px and angle <= angle_gate_deg
        output.append(
            {
                **row,
                "line_family_candidate": family,
                "residual_px": residual,
                "angle_residual_deg": angle,
                "accepted": accepted,
                "reason": "MODEL_LINE_SUPPORT" if accepted else "DISTANCE_OR_ORIENTATION_REJECTED",
            }
        )
    return output


def ground_region_mask(shape: tuple[int, int], polygon: np.ndarray) -> np.ndarray:
    """Create a conservative visible-ground polygon mask."""
    mask = np.zeros(shape, dtype=np.uint8)
    cv2.fillConvexPoly(mask, np.rint(polygon).astype(np.int32), 255)
    return mask


def support_foot_candidates(
    keypoints: list[dict[str, Any]], bbox: dict[str, float]
) -> dict[str, Any]:
    """Keep left/right candidates separate and select only with sufficient evidence."""
    by_name = {row["name"]: row for row in keypoints if row.get("visible", True)}
    candidates = {}
    for side in ("left", "right"):
        points = [
            by_name.get(f"{side}_{suffix}") for suffix in ("ankle", "heel", "big_toe", "small_toe")
        ]
        points = [point for point in points if point and float(point.get("confidence", 0)) >= 0.25]
        if points:
            weights = np.asarray([point["confidence"] for point in points], dtype=float)
            coordinates = np.asarray([[point["x"], point["y"]] for point in points], dtype=float)
            pixel = np.average(coordinates, axis=0, weights=weights)
            candidates[side] = {
                "pixel": pixel.tolist(),
                "confidence": float(weights.mean()),
                "names": [point["name"] for point in points],
                "vertical": float(pixel[1]),
            }
    fallback = [(float(bbox["x1"]) + float(bbox["x2"])) / 2, float(bbox["y2"])]
    if len(candidates) < 2:
        selected = max(candidates, key=lambda side: candidates[side]["confidence"], default=None)
        ambiguous = selected is None
    else:
        left, right = candidates["left"], candidates["right"]
        height = max(1.0, float(bbox["y2"]) - float(bbox["y1"]))
        vertical_gap = abs(left["vertical"] - right["vertical"])
        if vertical_gap < 0.025 * height:
            selected, ambiguous = None, True
        else:
            selected = "left" if left["vertical"] > right["vertical"] else "right"
            ambiguous = False
    return {
        "left": candidates.get("left"),
        "right": candidates.get("right"),
        "bbox_bottom": fallback,
        "selected_side": selected,
        "selected_pixel": candidates[selected]["pixel"] if selected else fallback,
        "ambiguous": ambiguous,
        "warnings": ["FOOT_SUPPORT_AMBIGUOUS"] if ambiguous else [],
    }


def optical_flow_step(
    previous: np.ndarray, current: np.ndarray, points: np.ndarray
) -> dict[str, Any]:
    """Track features one step and reject inconsistent forward/backward motion."""
    if len(points) == 0:
        return {
            "points": points,
            "displacement": [0.0, 0.0],
            "fb_error": float("inf"),
            "support": 0,
        }
    forward, status, _ = cv2.calcOpticalFlowPyrLK(previous, current, points, None)
    backward, reverse_status, _ = cv2.calcOpticalFlowPyrLK(current, previous, forward, None)
    valid = status[:, 0].astype(bool) & reverse_status[:, 0].astype(bool)
    errors = np.linalg.norm(backward - points, axis=2)[:, 0]
    valid &= errors <= 1.5
    if not valid.any():
        return {
            "points": points[:0],
            "displacement": [0.0, 0.0],
            "fb_error": float("inf"),
            "support": 0,
        }
    old, new = points[valid], forward[valid]
    displacement = np.median((new - old)[:, 0, :], axis=0)
    return {
        "points": new,
        "displacement": displacement.tolist(),
        "fb_error": float(np.median(errors[valid])),
        "support": int(valid.sum()),
    }


def far_evidence_decision(
    ground_valid: bool,
    temporal_support: int,
    identity_switches: int,
    calibration_spread_m: float,
    singularity_distance_px: float,
) -> str:
    """Accept distance-independent far evidence or leave it unresolved."""
    stable = (
        ground_valid
        and temporal_support >= 15
        and identity_switches == 0
        and calibration_spread_m <= 2.0
        and singularity_distance_px >= 25
    )
    return "accepted_observation" if stable else "unresolved"
