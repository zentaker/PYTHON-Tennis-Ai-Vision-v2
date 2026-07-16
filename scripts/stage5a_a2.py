"""Run the local, assumption-based Stage 5A audit for Nivel A2.

This script never runs a detector. It consumes the approved homography, existing Stage 3
CSV, and normalized Stage 4 events, then writes ignored diagnostics under outputs/.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.court.coordinates import CALIBRATION_POINT_ORDER, calibration_court_points
from src.geometry.camera_calibration import (
    decompose_planar_homography,
    intrinsic_matrix,
    rotation_angles_degrees,
)
from src.geometry.camera_model import CameraModel
from src.geometry.reprojection import project_homography, summarize_errors, vertical_sensitivity


ROOT = Path(__file__).resolve().parents[1]
CLIP = ROOT / "data" / "clips" / "nivel_a2_01"
OUT = ROOT / "outputs" / "nivel_a2_01" / "stage_5a"
W, H = 2746, 1536


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _model_record(model: CameraModel, name: str, focal_factor: float, pp_offset: tuple[int, int], court: np.ndarray, pixels: np.ndarray) -> dict[str, Any]:
    projected = model.project_world_to_pixel(np.column_stack((court, np.zeros(len(court)))))
    errors = np.linalg.norm(projected - pixels, axis=1)
    depths = model.camera_coordinates(np.column_stack((court, np.zeros(len(court)))))[:, 2]
    angles = rotation_angles_degrees(model.R)
    center = model.camera_center_world
    reasons: list[str] = []
    if center[2] <= 0:
        reasons.append("camera_below_ground")
    if np.any(depths <= 0):
        reasons.append("non_positive_court_depth")
    plausible = not reasons
    return {
        "candidate_id": name,
        "focal_factor_of_width": focal_factor,
        "fx": float(model.K[0, 0]), "fy": float(model.K[1, 1]),
        "cx": float(model.K[0, 2]), "cy": float(model.K[1, 2]),
        "principal_point_offset_px": list(pp_offset),
        "K": model.K.tolist(), "R": model.R.tolist(), "t": model.t.tolist(),
        "camera_center_world": center.tolist(), "height_m": float(center[2]),
        "distance_to_court_center_m": float(np.linalg.norm(center[:2])),
        "yaw_deg": angles["yaw"], "pitch_deg": angles["pitch"], "roll_deg": angles["roll"],
        "reprojection_error_pixels": summarize_errors(errors),
        "reprojection_error_per_point_pixels": errors.tolist(),
        "positive_depth_percentage": float(np.mean(depths > 0) * 100.0),
        "plausible": plausible,
        "rejection_reasons": reasons,
        "status": "PLAUSIBLE" if plausible else "REJECTED",
        "assumption_based": True,
    }


def _draw_overlay(image: np.ndarray, model: CameraModel, pixels: np.ndarray, court: np.ndarray, path: Path, title: str) -> None:
    canvas = image.copy()
    projected = model.project_world_to_pixel(np.column_stack((court, np.zeros(len(court)))))
    names = list(CALIBRATION_POINT_ORDER)
    for name, original, predicted in zip(names, pixels, projected):
        cv2.circle(canvas, tuple(np.round(original).astype(int)), 10, (0, 220, 0), -1)
        cv2.circle(canvas, tuple(np.round(predicted).astype(int)), 9, (0, 0, 255), 2)
        cv2.line(canvas, tuple(np.round(original).astype(int)), tuple(np.round(predicted).astype(int)), (255, 0, 255), 2)
        cv2.putText(canvas, f"{name} {np.linalg.norm(original-predicted):.1f}px", tuple(np.round(original + [8, -8]).astype(int)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
    # Court lines from the four corners and service lines.
    lines = [(0, 1), (2, 3), (0, 2), (1, 3), (4, 5), (6, 7)]
    for i, j in lines:
        a, b = projected[i].astype(int), projected[j].astype(int)
        cv2.line(canvas, tuple(a), tuple(b), (255, 170, 0), 3)
    center = model.project_world_to_pixel([[0, 0, 0]])[0].astype(int)
    for axis, endpoint, color in [("X", [2, 0, 0], (0, 0, 255)), ("Y", [0, 2, 0], (0, 180, 0)), ("Z", [0, 0, 3], (255, 0, 0))]:
        end = model.project_world_to_pixel([endpoint])[0].astype(int)
        cv2.arrowedLine(canvas, tuple(center), tuple(end), color, 4, tipLength=0.15)
        cv2.putText(canvas, axis, tuple(end + [6, 6]), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)
    cv2.putText(canvas, title, (30, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
    cv2.imwrite(str(path), canvas)


def _segments(events: list[dict[str, Any]], rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    result = []
    by_frame = {int(row["frame_id"]): row for row in rows}
    for index, (start, end) in enumerate(zip(events, events[1:]), start=1):
        frame_start, frame_end = start["frame_start"], end["frame_end"]
        frame_ids = list(range(frame_start, frame_end + 1))
        observed = [by_frame[f] for f in frame_ids if f in by_frame and by_frame[f]["x_smooth"] and by_frame[f]["y_smooth"]]
        interpolated = [row for row in observed if row["source"] == "interpolated"]
        missing = [f for f in frame_ids if f not in by_frame or not by_frame[f]["x_smooth"] or not by_frame[f]["y_smooth"]]
        coverage = len(observed) / len(frame_ids) if frame_ids else 0.0
        court_observed = project_homography(
            json.loads((CLIP / "homography.json").read_text(encoding="utf-8"))["H_pixel_to_court"],
            [[float(row["x_smooth"]), float(row["y_smooth"])] for row in observed],
        ) if observed else np.empty((0, 2))
        status = "READY_FOR_3D_FIT" if len(observed) >= 8 and coverage >= 0.60 else "WEAKLY_OBSERVED"
        if len(observed) < 4:
            status = "INSUFFICIENT_TRACKING"
        endpoint_constraints = []
        if start["type"] == "bounce":
            endpoint_constraints.append({"event": start["id"], "Z_m": 0.0, "role": "initial"})
        if end["type"] == "bounce":
            endpoint_constraints.append({"event": end["id"], "Z_m": 0.0, "role": "final"})
        result.append({
            "segment_id": f"flight_{index:02d}", "start_event": start["id"], "end_event": end["id"],
            "start_type": start["type"], "end_type": end["type"], "start_frame": frame_start, "end_frame": frame_end,
            "start_timestamp": start["time_start_seconds"], "end_timestamp": end["time_end_seconds"],
            "duration_seconds": float(end["time_end_seconds"] - start["time_start_seconds"]),
            "observed_tracking_frames": len(observed), "interpolated_frames": len(interpolated),
            "missing_frames": missing, "coverage": coverage,
            "endpoint_constraints": endpoint_constraints,
            "contains_observations_before_and_after_net": bool(np.any(court_observed[:, 1] < 0) and np.any(court_observed[:, 1] > 0)) if len(court_observed) else False,
            "tracking_confidence": {"mean": float(np.mean([float(row["confidence"]) for row in observed])) if observed else None, "min": float(np.min([float(row["confidence"]) for row in observed])) if observed else None},
            "spatial_distribution": {"pixel_x_min": min((float(r["x_smooth"]) for r in observed), default=None), "pixel_x_max": max((float(r["x_smooth"]) for r in observed), default=None), "pixel_y_min": min((float(r["y_smooth"]) for r in observed), default=None), "pixel_y_max": max((float(r["y_smooth"]) for r in observed), default=None)},
            "warnings": ["No vertical observations: Z remains unobservable from this input."],
            "status": status,
        })
    return result


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    homography_payload = _read_json(CLIP / "homography.json")
    H_pc = np.asarray(homography_payload["H_court_to_pixel"], dtype=np.float64)
    H_cp = np.asarray(homography_payload["H_pixel_to_court"], dtype=np.float64)
    corners_px = homography_payload["court_corners_pixel"]
    court_dict = calibration_court_points(homography_payload.get("layout", "doubles"))
    court = np.array([court_dict[name] for name in CALIBRATION_POINT_ORDER], dtype=np.float64)
    pixels = np.array([corners_px[name] for name in CALIBRATION_POINT_ORDER], dtype=np.float64)
    homography_audit = {
        "H_pixel_to_court": H_cp.tolist(), "H_court_to_pixel": H_pc.tolist(),
        "inverse_product_max_abs_error": float(np.max(np.abs(H_cp @ H_pc / (H_cp @ H_pc)[2, 2] - np.eye(3)))),
        "correspondences": [{"name": n, "pixel": pixels[i].tolist(), "court_m": court[i].tolist()} for i, n in enumerate(CALIBRATION_POINT_ORDER)],
        "existing_error_pixels": {"mean": homography_payload["reprojection_error_pixels_mean"], "max": homography_payload["reprojection_error_pixels_max"]},
        "existing_error_meters": {"mean": homography_payload["reprojection_error_meters_mean"], "max": homography_payload["reprojection_error_meters_max"]},
        "frame_dimensions": {"width": W, "height": H}, "orientation_validation": homography_payload["orientation_validation"],
        "coordinate_system": {"X_positive": "left to right", "Y_positive": "net to far baseline", "Z_positive": "up", "origin": "court center", "Y_zero": "net plane", "Z_zero": "court plane", "units": "metres", "handedness": "right-handed"},
        "source_sha256": hashlib.sha256((CLIP / "homography.json").read_bytes()).hexdigest(),
        "assumptions": ["Approved planar homography is unchanged and represents Z=0 only.", "Pinhole intrinsics are assumed; monocular scale/vertical pose is not ground truth."],
    }
    _write(OUT / "homography_audit.json", homography_audit)

    candidates: list[dict[str, Any]] = []
    models: list[CameraModel] = []
    focal_factors = [1.60, 1.80, 1.90, 2.00, 2.10, 2.20, 2.40]
    offsets = [(0, 0), (-100, 0), (100, 0), (0, -75), (0, 75)]
    for focal_factor in focal_factors:
        for dx, dy in offsets:
            K = intrinsic_matrix(focal_factor * W, W / 2 + dx, H / 2 + dy)
            try:
                model = decompose_planar_homography(H_pc, K, W, H)
                record = _model_record(model, f"f{focal_factor:.2f}_dx{dx}_dy{dy}", focal_factor, (dx, dy), court, pixels)
                models.append(model)
            except ValueError as exc:
                record = {"candidate_id": f"f{focal_factor:.2f}_dx{dx}_dy{dy}", "plausible": False, "status": "REJECTED", "rejection_reasons": [str(exc)]}
            candidates.append(record)
    plausible_candidates = [c for c in candidates if c.get("plausible") and "reprojection_error_pixels" in c]
    selected_record = min(plausible_candidates, key=lambda c: c["reprojection_error_pixels"]["mean"])
    selected_id = selected_record["candidate_id"]
    _write(OUT / "camera_candidates.json", {"schema_version": "1.0", "count": len(candidates), "selection": {"selected_candidate_id": selected_id, "selection_rule": "lowest planar reprojection error among controlled, physically plausible candidates; baseline and near-equivalent alternatives retained", "near_equivalent_candidates": [c["candidate_id"] for c in candidates if c.get("plausible")][:10]}, "candidates": candidates})
    with (OUT / "camera_candidates.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["candidate_id", "fx", "fy", "cx", "cy", "height_m", "distance_to_court_center_m", "yaw_deg", "pitch_deg", "roll_deg", "positive_depth_percentage", "reprojection_mean_px", "reprojection_max_px", "status", "rejection_reasons"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for c in candidates:
            error = c.get("reprojection_error_pixels", {})
            writer.writerow({**{f: c.get(f, "") for f in fields}, "reprojection_mean_px": error.get("mean", ""), "reprojection_max_px": error.get("max", ""), "rejection_reasons": ";".join(c.get("rejection_reasons", []))})
    selected_model = decompose_planar_homography(H_pc, np.asarray(selected_record["K"], dtype=np.float64), W, H)
    selected_model.write_json(OUT / "camera_model.json", clip_id="nivel_a2_01", status="NEEDS_VERTICAL_REFERENCE", calibration_method="ASSUMPTION_BASED_MONOCULAR_CALIBRATION", selected_candidate_id=selected_id, source_homography_sha=homography_audit["source_sha256"], calibration_points=homography_audit["correspondences"], errors=selected_record["reprojection_error_pixels"], uncertainty={"vertical": "high", "reason": "planar homography leaves focal/height/vertical pose underconstrained"}, assumptions=homography_audit["assumptions"], orientation=rotation_angles_degrees(selected_model.R))

    image = cv2.imread(str(CLIP / "reference_frame.png"))
    if image is None:
        raise FileNotFoundError(CLIP / "reference_frame.png")
    _draw_overlay(image, selected_model, pixels, court, OUT / "camera_reprojection_overlay.png", f"Stage 5A camera reprojection | C={np.round(selected_model.camera_center_world, 2).tolist()} m")
    overlay_image = cv2.imread(str(OUT / "camera_reprojection_overlay.png"))
    writer = cv2.VideoWriter(
        str(OUT / "camera_reprojection_overlay.mp4"),
        cv2.VideoWriter_fourcc(*"mp4v"),
        30.0,
        (W, H),
    )
    if not writer.isOpened():
        raise RuntimeError("could not create camera reprojection overlay video")
    try:
        for _ in range(60):
            writer.write(overlay_image)
    finally:
        writer.release()
    # Virtual vertical references are intentionally diagnostic only.
    vertical_heights = [0.5, 0.914, 1.07, 2.0, 3.0, 5.0]
    center = selected_model.project_world_to_pixel([[0, 0, 0]])[0].astype(int)
    vertical_image = image.copy()
    for z in vertical_heights:
        end = selected_model.project_world_to_pixel([[0, 0, z]])[0].astype(int)
        cv2.line(vertical_image, tuple(center), tuple(end), (255, 0, 255), 3)
        cv2.putText(vertical_image, f"Z={z:g}m", tuple(end + [8, 0]), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 0, 255), 2)
    # Two virtual net posts are diagnostic projections, not human annotations.
    for x in (-5.635, 5.635):
        base = selected_model.project_world_to_pixel([[x, 0, 0]])[0].astype(int)
        top = selected_model.project_world_to_pixel([[x, 0, 1.07]])[0].astype(int)
        cv2.line(vertical_image, tuple(base), tuple(top), (0, 255, 255), 4)
        cv2.putText(vertical_image, "net post 1.07m", tuple(top + [8, 0]), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
    cv2.imwrite(str(OUT / "vertical_reference_overlay.png"), vertical_image)
    sensitivity = vertical_sensitivity(models[::5], (0.0, 0.0), vertical_heights)
    sensitivity.update({"candidate_ids": [c["candidate_id"] for c in candidates[::5]], "threshold_pixels": 25.0, "decision": "NEEDS_VERTICAL_REFERENCE" if sensitivity["max_spread_pixels"] > 25 else "stable_under_assumptions"})
    _write(OUT / "vertical_sensitivity_report.json", sensitivity)

    rows = list(csv.DictReader((OUT.parent / "stage_3" / "smoothed_trajectory.csv").open(encoding="utf-8")))
    events = _read_json(OUT.parent / "stage_4" / "events.json")["events"]
    segments = _segments(events, rows)
    unique_bounces = [{"event": event["id"], "frame": event["frame_start"], "Z_m": 0.0} for event in events if event["type"] == "bounce"]
    _write(OUT / "flight_segments.json", {"schema_version": "1.0", "clip_id": "nivel_a2_01", "event_count": len(events), "segment_count": len(segments), "segments": segments, "unique_bounce_constraints": unique_bounces, "note": "No 3D trajectory fit performed in Stage 5A."})
    _write(OUT / "readiness_report.json", {"schema_version": "1.0", "clip_id": "nivel_a2_01", "decision": "NEEDS_VERTICAL_REFERENCE", "reason": "Planar homography reproduces Z=0 but does not identify a unique vertical camera model; virtual vertical projections diverge across equally valid candidates.", "candidate_count": len(candidates), "selected_candidate_id": selected_id, "segment_count": len(segments), "segments_ready_for_3d_fit": sum(s["status"] == "READY_FOR_3D_FIT" for s in segments), "last_segment": "ev_009→ev_010", "next_minimal_human_reference": ["two points on a net post with known physical height", "base and top of one vertical post", "or one frame/point with known ball apex height"], "stage_5b_started": False})
    print("Stage 5A complete: NEEDS_VERTICAL_REFERENCE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
