"""Real metric-based readiness evaluation for the saved vertical reference."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.court.coordinates import CALIBRATION_POINT_ORDER
from src.geometry.camera_model import CameraModel
from src.geometry.camera_calibration import rotation_angles_degrees
from src.geometry.reprojection import summarize_errors
from src.geometry.vertical_calibration import refine_pinhole_camera


GROUND_NAMES = CALIBRATION_POINT_ORDER
HEIGHTS = [0.5, 0.914, 1.07, 2.0, 3.0, 5.0]
JITTER_SEED = 20260716
JITTER_SAMPLES = 200


def _world_pixels(homography: dict[str, Any], references: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    ground_world = np.asarray([[*homography["court_corners_court_meters"][name], 0.0] for name in GROUND_NAMES], dtype=np.float64)
    ground_pixels = np.asarray([homography["court_corners_pixel"][name] for name in GROUND_NAMES], dtype=np.float64)
    vertical_world = np.asarray([item["world"] for item in references], dtype=np.float64)
    vertical_pixels = np.asarray([item["pixel"] for item in references], dtype=np.float64)
    return ground_world, ground_pixels, vertical_world, vertical_pixels


def _candidate_model(record: dict[str, Any], template: CameraModel) -> CameraModel:
    return CameraModel(record["K"], record["R"], record["t"], template.image_width, template.image_height, template.coordinate_system)


def _model_metrics(model: CameraModel, ground_world: np.ndarray, ground_pixels: np.ndarray, vertical_world: np.ndarray, vertical_pixels: np.ndarray) -> dict[str, Any]:
    ground_errors = model.reprojection_error(ground_world, ground_pixels)
    vertical_errors = model.reprojection_error(vertical_world, vertical_pixels)
    vertical_projected = model.project_world_to_pixel(vertical_world)
    vertical_residuals = vertical_projected - vertical_pixels
    depths = np.concatenate([model.camera_coordinates(ground_world)[:, 2], model.camera_coordinates(vertical_world)[:, 2]])
    return {
        "ground_errors_px": ground_errors.tolist(),
        "vertical_errors_px": vertical_errors.tolist(),
        "ground": summarize_errors(ground_errors),
        "vertical": summarize_errors(vertical_errors),
        "vertical_reprojection": [{"id": name, "human_pixel": vertical_pixels[index].tolist(), "reprojected_pixel": vertical_projected[index].tolist(), "dx_px": float(vertical_residuals[index, 0]), "dy_px": float(vertical_residuals[index, 1]), "error_px": float(vertical_errors[index]), "horizontal_abs_px": float(abs(vertical_residuals[index, 0])), "vertical_abs_px": float(abs(vertical_residuals[index, 1]))} for index, name in enumerate((item["id"] for item in []))],
        "positive_depth_percentage": float(np.mean(depths > 0) * 100),
        "camera_above_ground": bool(model.camera_center_world[2] > 0),
        "rotation_orthonormal": bool(np.allclose(model.R.T @ model.R, np.eye(3), atol=1e-5)),
        "rotation_det": float(np.linalg.det(model.R)),
    }


def _vertical_reprojection(model: CameraModel, references: list[dict[str, Any]], vertical_world: np.ndarray, vertical_pixels: np.ndarray) -> list[dict[str, Any]]:
    projected = model.project_world_to_pixel(vertical_world)
    residuals = projected - vertical_pixels
    errors = np.linalg.norm(residuals, axis=1)
    return [{"id": references[index]["id"], "human_pixel": vertical_pixels[index].tolist(), "reprojected_pixel": projected[index].tolist(), "dx_px": float(residuals[index, 0]), "dy_px": float(residuals[index, 1]), "error_px": float(errors[index]), "horizontal_abs_px": float(abs(residuals[index, 0])), "vertical_abs_px": float(abs(residuals[index, 1]))} for index in range(len(references))]


def _distribution(values: np.ndarray) -> dict[str, float]:
    return {"mean": float(np.mean(values)), "std": float(np.std(values)), "p05": float(np.percentile(values, 5)), "p50": float(np.percentile(values, 50)), "p95": float(np.percentile(values, 95)), "min": float(np.min(values)), "max": float(np.max(values))}


def classify_readiness(passed: dict[str, bool], vertical_mean: float, vertical_max: float, improvement_percentage: float, *, invalid_reference: bool = False) -> str:
    """Apply documented thresholds without depending on optimizer convergence."""
    if invalid_reference:
        return "INVALID_HUMAN_REFERENCE"
    if all(passed.values()):
        return "READY_FOR_STAGE_5B"
    if vertical_mean <= 5 and vertical_max <= 10 and improvement_percentage >= 50:
        return "MARGINAL_VERTICAL_CALIBRATION"
    return "STILL_NEEDS_VERTICAL_REFERENCE"


def jitter_analysis(initial: CameraModel, references: list[dict[str, Any]], ground_world: np.ndarray, ground_pixels: np.ndarray, *, samples: int = JITTER_SAMPLES) -> dict[str, Any]:
    vertical_world = np.asarray([item["world"] for item in references], dtype=np.float64)
    original_pixels = np.asarray([item["pixel"] for item in references], dtype=np.float64)
    levels: dict[str, Any] = {}
    for level in (1, 2, 3):
        rng = np.random.default_rng(JITTER_SEED + level)
        perturbations = rng.uniform(-level, level, size=(samples, 4, 2))
        heights: list[float] = []
        focals: list[float] = []
        ground_means: list[float] = []
        vertical_means: list[float] = []
        centers: list[np.ndarray] = []
        angles: list[dict[str, float]] = []
        projections = {str(height): [] for height in HEIGHTS}
        valid = 0
        for perturbation in perturbations:
            pixels = original_pixels + perturbation
            try:
                model, _metrics = refine_pinhole_camera(initial, np.vstack([ground_world, vertical_world]), np.vstack([ground_pixels, pixels]), max_nfev=500)
                metric = model.reprojection_error(ground_world, ground_pixels)
                vertical_error = model.reprojection_error(vertical_world, pixels)
                if not model.camera_center_world[2] > 0:
                    continue
            except (ValueError, np.linalg.LinAlgError, RuntimeError):
                continue
            valid += 1
            heights.append(float(model.height_m))
            focals.append(float(np.mean([model.K[0, 0], model.K[1, 1]])))
            ground_means.append(float(metric.mean()))
            vertical_means.append(float(vertical_error.mean()))
            centers.append(model.camera_center_world.copy())
            angles.append(rotation_angles_degrees(model.R))
            for height in HEIGHTS:
                projections[str(height)].append(model.project_world_to_pixel([[0, 0, height]])[0])
        if valid < samples:
            raise ValueError(f"Only {valid}/{samples} jitter solutions were valid at ±{level}px")
        displacement: dict[str, dict[str, float]] = {}
        for height, values in projections.items():
            array = np.asarray(values)
            center = np.median(array, axis=0)
            distances = np.linalg.norm(array - center, axis=1)
            displacement[height] = {**_distribution(distances), "spread_x_px": float(np.ptp(array[:, 0])), "spread_y_px": float(np.ptp(array[:, 1])), "max_spread_px": float(np.max(np.ptp(array, axis=0)))}
        center_array = np.asarray(centers)
        angle_distributions = {name: _distribution(np.asarray([angle[name] for angle in angles])) for name in ("yaw", "pitch", "roll")}
        levels[str(level)] = {"level_px": level, "samples": valid, "seed": JITTER_SEED + level, "height_m": _distribution(np.asarray(heights)), "focal_px": _distribution(np.asarray(focals)), "camera_center_world": {axis: _distribution(center_array[:, index]) for index, axis in enumerate(("x", "y", "z"))}, "orientation_deg": angle_distributions, "ground_mean_px": _distribution(np.asarray(ground_means)), "vertical_mean_px": _distribution(np.asarray(vertical_means)), "virtual_projection_displacement": displacement}
    return {"seed": JITTER_SEED, "samples_per_level": samples, "heights_m": HEIGHTS, "levels": levels}


def evaluate_vertical_calibration(initial: CameraModel, candidates_payload: dict[str, Any], homography: dict[str, Any], references: list[dict[str, Any]], *, original_sensitivity_px: float = 117.5) -> dict[str, Any]:
    ground_world, ground_pixels, vertical_world, vertical_pixels = _world_pixels(homography, references)
    candidate_results: list[dict[str, Any]] = []
    models: dict[str, CameraModel] = {}
    for record in candidates_payload.get("candidates", []):
        try:
            candidate_initial = _candidate_model(record, initial)
            model, optimizer = refine_pinhole_camera(candidate_initial, np.vstack([ground_world, vertical_world]), np.vstack([ground_pixels, vertical_pixels]))
            metrics = _model_metrics(model, ground_world, ground_pixels, vertical_world, vertical_pixels)
            metrics["vertical_reprojection"] = _vertical_reprojection(model, references, vertical_world, vertical_pixels)
            score = float(metrics["ground"]["mean"] + metrics["vertical"]["mean"] + max(0.0, metrics["ground"]["max"] - 8.0) * 0.5)
            candidate_results.append({"candidate_id": record["candidate_id"], "score": score, "optimizer": optimizer, "camera_center_world": model.camera_center_world.tolist(), "height_m": model.height_m, "fx": float(model.K[0, 0]), "fy": float(model.K[1, 1]), "metrics": metrics, "model": model.to_dict()})
            models[record["candidate_id"]] = model
        except (ValueError, np.linalg.LinAlgError, RuntimeError) as exc:
            candidate_results.append({"candidate_id": record.get("candidate_id", "unknown"), "status": "REJECTED", "reason": str(exc)})
    valid = [item for item in candidate_results if "model" in item]
    if not valid:
        return {"status": "INVALID_HUMAN_REFERENCE", "candidate_results": candidate_results, "failed_criteria": ["no_valid_candidate"]}
    selected = min(valid, key=lambda item: item["score"])
    selected_model = models[selected["candidate_id"]]
    jitter = jitter_analysis(selected_model, references, ground_world, ground_pixels)
    metrics = selected["metrics"]
    vertical_bias = float(np.mean([item["dy_px"] for item in metrics["vertical_reprojection"]]))
    p95_3m = jitter["levels"]["2"]["virtual_projection_displacement"]["3.0"]["p95"]
    p95_5m = jitter["levels"]["2"]["virtual_projection_displacement"]["5.0"]["p95"]
    height_dist = jitter["levels"]["2"]["height_m"]
    height_variation = float((height_dist["p95"] - height_dist["p05"]) / max(abs(height_dist["p50"]), 1e-9))
    near = [item for item in valid if item["score"] <= selected["score"] * 1.1]
    passed = {
        "four_references_valid": True,
        "positive_depths": metrics["positive_depth_percentage"] == 100.0,
        "camera_above_ground": metrics["camera_above_ground"],
        "rotation_valid": metrics["rotation_orthonormal"] and abs(metrics["rotation_det"] - 1) <= 1e-5,
        "vertical_mean_le_5px": metrics["vertical"]["mean"] <= 5,
        "vertical_max_le_10px": metrics["vertical"]["max"] <= 10,
        "ground_mean_le_8px": metrics["ground"]["mean"] <= 8,
        "ground_max_le_18px": metrics["ground"]["max"] <= 18,
        "jitter_p95_3m_le_15px": p95_3m <= 15,
        "jitter_p95_5m_le_25px": p95_5m <= 25,
        "height_variation_p95_le_15pct": height_variation <= 0.15,
        "narrow_or_preferable_family": len(near) == 1 or (max(item["score"] for item in near) - min(item["score"] for item in near) < 1.0),
        "no_vertical_bias": abs(vertical_bias) <= 5,
    }
    failed = [name for name, value in passed.items() if not value]
    sensitivity_after = float(max(jitter["levels"]["2"]["virtual_projection_displacement"]["3.0"]["max_spread_px"], jitter["levels"]["2"]["virtual_projection_displacement"]["5.0"]["max_spread_px"]))
    improvement = float((1 - sensitivity_after / original_sensitivity_px) * 100)
    status = classify_readiness(passed, metrics["vertical"]["mean"], metrics["vertical"]["max"], improvement)
    return {"status": status, "selected": selected, "candidate_results": [{key: value for key, value in item.items() if key != "model"} for item in candidate_results], "selected_model": selected_model, "metrics": {**metrics, "vertical_bias_y_px": vertical_bias}, "criteria": {"passed": [name for name, value in passed.items() if value], "failed": failed, "values": {"jitter_p95_3m_px": p95_3m, "jitter_p95_5m_px": p95_5m, "height_variation_p95": height_variation}}, "jitter": jitter, "sensitivity_before_px": original_sensitivity_px, "sensitivity_after_px": sensitivity_after, "improvement_percentage": improvement, "recommendation": "Proceed to Stage 5B only if all criteria pass." if status == "READY_FOR_STAGE_5B" else "Do not start Stage 5B; retain the saved references and review failed criteria."}


def write_candidate_csv(path: Path, candidate_results: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["candidate_id", "score", "height_m", "fx", "fy", "ground_mean_px", "ground_max_px", "vertical_mean_px", "vertical_max_px", "positive_depth_percentage", "status"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in candidate_results:
            metrics = item.get("metrics", {})
            ground = metrics.get("ground", {})
            vertical = metrics.get("vertical", {})
            writer.writerow({"candidate_id": item.get("candidate_id"), "score": item.get("score"), "height_m": item.get("height_m"), "fx": item.get("fx"), "fy": item.get("fy"), "ground_mean_px": ground.get("mean"), "ground_max_px": ground.get("max"), "vertical_mean_px": vertical.get("mean"), "vertical_max_px": vertical.get("max"), "positive_depth_percentage": metrics.get("positive_depth_percentage"), "status": item.get("status", "VALID")})


def render_vertical_overlays(
    frame_path: Path,
    output_overlay: Path,
    output_closeup: Path,
    model: CameraModel,
    homography: dict[str, Any],
    references: list[dict[str, Any]],
) -> None:
    image = cv2.imread(str(frame_path))
    if image is None:
        raise FileNotFoundError(frame_path)
    canvas = image.copy()
    vertical_world = np.asarray([item["world"] for item in references], dtype=np.float64)
    vertical_pixels = np.asarray([item["pixel"] for item in references], dtype=np.float64)
    projected = model.project_world_to_pixel(vertical_world)
    for index, item in enumerate(references):
        human = tuple(np.round(vertical_pixels[index]).astype(int))
        reproj = tuple(np.round(projected[index]).astype(int))
        color = (0, 220, 255) if item["world"][2] == 0 else (255, 0, 255)
        cv2.circle(canvas, human, 12, (0, 255, 0), -1)
        cv2.circle(canvas, reproj, 11, color, 3)
        cv2.line(canvas, human, reproj, (255, 80, 0), 3)
        cv2.putText(canvas, f"{item['id']} err={np.linalg.norm(projected[index]-vertical_pixels[index]):.1f}px", (human[0] + 10, human[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
    ground = np.asarray([homography["court_corners_court_meters"][name] for name in GROUND_NAMES], dtype=np.float64)
    ground_projected = model.project_world_to_pixel(np.column_stack((ground, np.zeros(len(ground)))))
    for first, second in ((0, 1), (2, 3), (0, 2), (1, 3)):
        cv2.line(canvas, tuple(ground_projected[first].astype(int)), tuple(ground_projected[second].astype(int)), (255, 170, 0), 3)
    center = model.project_world_to_pixel([[0, 0, 0]])[0].astype(int)
    for axis, point, color in (("X", [2, 0, 0], (0, 0, 255)), ("Y", [0, 2, 0], (0, 180, 0)), ("Z", [0, 0, 3], (255, 0, 0))):
        endpoint = model.project_world_to_pixel([point])[0].astype(int)
        cv2.arrowedLine(canvas, tuple(center), tuple(endpoint), color, 4, tipLength=0.15)
        cv2.putText(canvas, axis, tuple(endpoint + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 3)
    for height in HEIGHTS:
        endpoint = model.project_world_to_pixel([[0, 0, height]])[0].astype(int)
        cv2.line(canvas, tuple(center), tuple(endpoint), (255, 0, 255), 2)
        cv2.putText(canvas, f"Z={height:g}m", tuple(endpoint + [8, 0]), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 0, 255), 2)
    cv2.putText(canvas, "Verde=humano  Magenta/Cian=reproyectado  Naranja=error", (25, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 3)
    output_overlay.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_overlay), canvas)
    points = np.vstack([vertical_pixels, projected])
    x0, y0 = np.min(points, axis=0) - 180
    x1, y1 = np.max(points, axis=0) + 180
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(image.shape[1], int(x1)), min(image.shape[0], int(y1))
    crop = canvas[y0:y1, x0:x1]
    output_closeup.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_closeup), crop)
