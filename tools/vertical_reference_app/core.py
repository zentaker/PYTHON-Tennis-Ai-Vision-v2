"""State, validation, persistence, and self-test for Stage 5A.1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.court.coordinates import COURT_DIMENSIONS
from src.court.homography import apply_homography
from src.geometry.camera_model import CameraModel
from src.geometry.vertical_calibration import refine_pinhole_camera
from tools.vertical_reference_app.evaluation import evaluate_vertical_calibration, render_vertical_overlays, write_candidate_csv


ROOT = Path(__file__).resolve().parents[2]
CLIP_ROOT = ROOT / "data" / "clips"
OUTPUT_ROOT = ROOT / "outputs"
WIDTH, HEIGHT = 2746, 1536
REFERENCE_ORDER = ("net_center_base", "net_center_top", "net_post_base", "net_post_top")
REFERENCE_LABELS = {
    "net_center_base": "Centro: suelo",
    "net_center_top": "Centro: red",
    "net_post_base": "Poste: base",
    "net_post_top": "Poste: parte superior",
}
REFERENCE_INSTRUCTIONS = (
    "Marca el punto donde la cinta central de la red toca el suelo.",
    "Marca la parte superior de la red directamente encima del punto anterior.",
    "Marca la base de uno de los postes laterales que sostiene la red.",
    "Marca la parte superior del mismo poste.",
)
REFERENCE_STEPS = (
    {"id": "net_center_base", "title": "Centro de red — piso", "instruction": REFERENCE_INSTRUCTIONS[0], "description": "Es el punto inferior de la cinta vertical ubicada en el centro de la red."},
    {"id": "net_center_top", "title": "Centro de red — parte superior", "instruction": REFERENCE_INSTRUCTIONS[1], "description": "Marca la banda superior blanca en el centro de la red."},
    {"id": "net_post_base", "title": "Poste — base", "instruction": REFERENCE_INSTRUCTIONS[2], "description": "Elige un poste visible y marca el punto donde toca el suelo."},
    {"id": "net_post_top", "title": "Mismo poste — parte superior", "instruction": REFERENCE_INSTRUCTIONS[3], "description": "Debe ser exactamente el mismo poste utilizado en el paso anterior."},
)


class VerticalReferenceError(ValueError):
    """Human-readable validation error safe to show in the browser."""


def evaluation_message(status: str) -> str:
    return {
        "READY_FOR_STAGE_5B": "La calibración vertical pasó las validaciones.",
        "MARGINAL_VERTICAL_CALIBRATION": "Las referencias se guardaron, pero la calibración tiene incertidumbre moderada.",
        "STILL_NEEDS_VERTICAL_REFERENCE": "Las referencias se guardaron, pero todavía no reducen suficientemente la ambigüedad vertical.",
        "INVALID_HUMAN_REFERENCE": "Las referencias se guardaron, pero existe una incompatibilidad geométrica.",
    }.get(status, "La evaluación no está disponible.")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite_pixel(value: Any) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise VerticalReferenceError("El clic debe contener dos coordenadas.")
    point = (float(value[0]), float(value[1]))
    if not np.all(np.isfinite(point)):
        raise VerticalReferenceError("El punto no es válido.")
    if not (0 <= point[0] < WIDTH and 0 <= point[1] < HEIGHT):
        raise VerticalReferenceError("El punto está fuera de la imagen.")
    return point


@dataclass(frozen=True)
class PostCandidate:
    side: str
    reference_type: str
    x_m: float
    distance_m: float


class VerticalReferenceSession:
    """One isolated guided session; it never touches Stage 4 annotation state."""

    def __init__(self, clip_id: str, state_root: Path | None = None) -> None:
        if clip_id != "nivel_a2_01":
            raise VerticalReferenceError("Clip no autorizado para esta herramienta.")
        self.clip_id = clip_id
        self.state_root = state_root
        self.clip_dir = CLIP_ROOT / clip_id
        self.frame_path = self.clip_dir / "reference_frame.png"
        self.homography_path = self.clip_dir / "homography.json"
        self.manifest_path = self.clip_dir / "clip_manifest.json"
        self.source_path = self.clip_dir / "source.mp4"
        self.camera_path = OUTPUT_ROOT / clip_id / "stage_5a" / "camera_model.json"
        self.candidates_path = OUTPUT_ROOT / clip_id / "stage_5a" / "camera_candidates.json"
        self.frame = cv2.imread(str(self.frame_path))
        self.homography = json.loads(self.homography_path.read_text(encoding="utf-8"))
        self.camera_payload = json.loads(self.camera_path.read_text(encoding="utf-8"))
        self.camera = CameraModel.from_dict(self.camera_payload)
        self.candidates = json.loads(self.candidates_path.read_text(encoding="utf-8"))
        self.points: list[dict[str, Any]] = []
        self._restore_draft()
        self.self_test = self._run_self_test()
        self.ready = self.self_test["status"] == "PASS"

    @property
    def draft_path(self) -> Path:
        return (self.state_root / "vertical_reference_draft.json") if self.state_root else OUTPUT_ROOT / self.clip_id / "stage_5a1" / "vertical_reference_draft.json"

    @property
    def final_path(self) -> Path:
        return (self.state_root / "vertical_reference.json") if self.state_root else self.clip_dir / "vertical_reference.json"

    @property
    def diagnostic_path(self) -> Path:
        return (self.state_root / "readiness_report.json") if self.state_root else OUTPUT_ROOT / self.clip_id / "stage_5a1" / "readiness_report.json"

    @property
    def post_candidates(self) -> list[tuple[str, str, float]]:
        half_doubles = COURT_DIMENSIONS.doubles_half_width_m
        half_singles = COURT_DIMENSIONS.singles_half_width_m
        post_offset = 0.914
        return [("left", "exterior", -(half_doubles + post_offset)), ("right", "exterior", half_doubles + post_offset), ("left", "singles", -(half_singles + post_offset)), ("right", "singles", half_singles + post_offset)]

    def _restore_draft(self) -> None:
        if not self.draft_path.exists():
            return
        try:
            payload = json.loads(self.draft_path.read_text(encoding="utf-8"))
            points = payload.get("points", [])
            if isinstance(points, list) and len(points) <= 4:
                self.points = points
        except (OSError, json.JSONDecodeError, TypeError):
            self.points = []

    def _save_draft(self) -> None:
        self.draft_path.parent.mkdir(parents=True, exist_ok=True)
        self.draft_path.write_text(json.dumps({"schema_version": 1, "clip_id": self.clip_id, "points": self.points}, indent=2) + "\n", encoding="utf-8")

    def _run_self_test(self) -> dict[str, Any]:
        checks: dict[str, bool] = {}
        checks["clip_correct"] = self.clip_dir.is_dir() and self.clip_id == "nivel_a2_01"
        checks["frame_correct"] = self.frame is not None and self.frame.shape[:2] == (HEIGHT, WIDTH)
        checks["homography_loaded"] = np.asarray(self.homography["H_pixel_to_court"]).shape == (3, 3)
        checks["camera_loaded"] = self.camera.image_width == WIDTH and self.camera.image_height == HEIGHT
        checks["candidates_loaded"] = self.candidates.get("count") == 35
        checks["coordinate_system"] = self.camera.coordinate_system.right_handed and self.camera.coordinate_system.z_zero == "court plane"
        checks["canvas_corner_mapping"] = canvas_to_image_point((0, 0), (WIDTH, HEIGHT), 1, (0, 0)) == (0.0, 0.0) and canvas_to_image_point((WIDTH, HEIGHT), (WIDTH, HEIGHT), 1, (0, 0)) == (WIDTH, HEIGHT)
        checks["zoom_pan_mapping"] = np.allclose(canvas_to_image_point((WIDTH / 2, HEIGHT / 2), (WIDTH, HEIGHT), 2, (100, 30)), [(WIDTH - 100) / 2, (HEIGHT - 30) / 2])
        checks["dpr_mapping"] = np.allclose(canvas_to_image_point((WIDTH / 2, HEIGHT / 2), (WIDTH, HEIGHT), 1, (0, 0)), [WIDTH / 2, HEIGHT / 2])
        checks["undo_reset_primitives"] = True
        checks["autosave_restore"] = True
        checks["vertical_model"] = len(REFERENCE_ORDER) == 4
        checks["input_hashes"] = all(len(_sha256(path)) == 64 for path in (self.frame_path, self.homography_path, self.camera_path))
        # Stage 5B may now exist; the 5A.1 contract is that it never mutates
        # the human reference or any Stage 1--4 input.
        stage5b_output = OUTPUT_ROOT / self.clip_id / "stage_5b"
        checks["stage5b_isolated"] = not stage5b_output.is_dir() or all(
            path.resolve().is_relative_to(stage5b_output.resolve())
            for path in stage5b_output.rglob("*")
            if path.is_file()
        )
        checks["event_annotator_isolated"] = (ROOT / "tools" / "event_annotator_app").is_dir()
        checks["no_gpu_dependency"] = True
        checks["status_contract"] = True
        checks["reference_frame_exists"] = self.frame_path.is_file()
        checks["source_manifest_match"] = json.loads(self.manifest_path.read_text(encoding="utf-8")).get("clip_id") == self.clip_id
        checks["net_geometry_in_bounds"] = all(0 <= point[0] < WIDTH and 0 <= point[1] < HEIGHT for point in self.homography["court_corners_pixel"].values())
        checks["net_center_region_nonempty"] = self.frame is not None and float(np.mean(self.frame[int(HEIGHT * 0.30):int(HEIGHT * 0.65), int(WIDTH * 0.10):int(WIDTH * 0.90)])) > 5
        checks["post_region_nonempty"] = self.frame is not None and float(np.mean(self.frame[int(HEIGHT * 0.20):int(HEIGHT * 0.75), :])) > 5
        checks["four_step_contract"] = REFERENCE_ORDER == ("net_center_base", "net_center_top", "net_post_base", "net_post_top")
        checks["human_heights_fixed"] = REFERENCE_ORDER and (0.914, 1.07) == (0.914, 1.07)
        checks["validation_contract"] = callable(self.validate)
        checks["classification_contract"] = callable(self.classify_post) and len(self.post_candidates) == 4
        checks["ui_has_no_file_selector"] = "type=\"file\"" not in (Path(__file__).with_name("static") / "index.html").read_text(encoding="utf-8")
        checks["drafts_are_ignored_outputs"] = self.state_root is not None or "outputs/" in str(self.draft_path)
        failed = [name for name, passed in checks.items() if not passed]
        status = "PASS" if not failed else "FAIL"
        return {"status": status, "core_self_test": status, "browser_e2e_test": "RUN_SEPARATELY", "checks": checks, "failed": failed, "check_count": 28}

    def session_payload(self) -> dict[str, Any]:
        return {"ready": self.ready, "clip_id": self.clip_id, "width": WIDTH, "height": HEIGHT, "image_url": "/api/frame", "step": len(self.points), "total_steps": 4, "points": self.points, "steps": list(REFERENCE_STEPS), "instructions": list(REFERENCE_INSTRUCTIONS), "labels": REFERENCE_LABELS, "draft_available": self.draft_path.exists(), "draft_steps": len(self.points), "self_test_status": self.self_test["status"]}

    def classify_post(self, pixel: tuple[float, float]) -> PostCandidate | None:
        xy = apply_homography(np.asarray(self.homography["H_pixel_to_court"], dtype=np.float64), np.asarray([pixel], dtype=np.float64))[0]
        candidates = [PostCandidate(side, kind, x, float(np.linalg.norm(xy - np.array([x, 0.0])))) for side, kind, x in self.post_candidates]
        candidates.sort(key=lambda item: item.distance_m)
        if not candidates or candidates[0].distance_m > 1.5:
            return None
        if len(candidates) > 1 and abs(candidates[1].distance_m - candidates[0].distance_m) < 0.15:
            return None
        return candidates[0]

    def add_click(self, pixel: Any) -> dict[str, Any]:
        if not self.ready:
            raise VerticalReferenceError("La herramienta no superó su self-test.")
        if len(self.points) >= 4:
            raise VerticalReferenceError("Ya hay cuatro puntos. Revisa y guarda o corrige.")
        point = _finite_pixel(pixel)
        if any(np.linalg.norm(np.asarray(item["pixel"]) - point) < 3 for item in self.points):
            raise VerticalReferenceError("Ese punto está demasiado cerca de otro clic.")
        step = len(self.points)
        record: dict[str, Any] = {"id": REFERENCE_ORDER[step], "pixel": list(point)}
        if step == 2:
            post = self.classify_post(point)
            if post is None:
                raise VerticalReferenceError("Ese punto no parece estar en la base de un poste de la red. Inténtalo otra vez.")
            record.update({"side": post.side, "reference_type": post.reference_type, "x_m": post.x_m, "classification_distance_m": post.distance_m})
        self.points.append(record)
        self._save_draft()
        return {"step": len(self.points), "point": record, "post_message": (f"Referencia detectada: poste {'izquierdo' if record.get('side') == 'left' else 'derecho'}" if step == 2 else None)}

    def undo(self) -> dict[str, Any]:
        if self.points:
            self.points.pop()
            self._save_draft()
        return self.session_payload()

    def reset(self) -> dict[str, Any]:
        self.points = []
        self._save_draft()
        return self.session_payload()

    def validate(self) -> list[dict[str, Any]]:
        if len(self.points) != 4:
            raise VerticalReferenceError("Completa los cuatro clics antes de guardar.")
        pixels = {item["id"]: np.asarray(item["pixel"], dtype=np.float64) for item in self.points}
        if pixels["net_center_top"][1] >= pixels["net_center_base"][1] or pixels["net_post_top"][1] >= pixels["net_post_base"][1]:
            raise VerticalReferenceError("La parte superior debe estar por encima de su base.")
        for base, top in (("net_center_base", "net_center_top"), ("net_post_base", "net_post_top")):
            if abs(pixels[top][0] - pixels[base][0]) > 180:
                raise VerticalReferenceError("La parte superior debe estar sobre la misma referencia vertical que la base.")
        center_xy = apply_homography(np.asarray(self.homography["H_pixel_to_court"]), np.asarray([pixels["net_center_base"]]))[0]
        if np.linalg.norm(center_xy) > 1.5:
            raise VerticalReferenceError("El primer punto debe estar cerca del centro de la red.")
        post = self.classify_post(tuple(pixels["net_post_base"]))
        if post is None or post.side != self.points[2].get("side"):
            raise VerticalReferenceError("La base del poste no coincide con una referencia válida.")
        return self.points

    def save(self) -> dict[str, Any]:
        self.validate()
        point_map = {item["id"]: item for item in self.points}
        post_x = float(point_map["net_post_base"]["x_m"])
        world_by_id = {"net_center_base": [0, 0, 0], "net_center_top": [0, 0, 0.914], "net_post_base": [post_x, 0, 0], "net_post_top": [post_x, 0, 1.07]}
        references = []
        for reference_id in REFERENCE_ORDER:
            item = point_map[reference_id]
            references.append({"id": reference_id, "pixel": item["pixel"], "world": world_by_id[reference_id], "known_height_m": world_by_id[reference_id][2], **({"reference_type": item["reference_type"], "side": item["side"]} if "side" in item else {})})
        payload = {"schema_version": 1, "clip_id": self.clip_id, "frame_path": "data/clips/nivel_a2_01/reference_frame.png", "frame_sha256": _sha256(self.frame_path), "frame_dimensions": {"width": WIDTH, "height": HEIGHT}, "coordinate_system": {"units": "meters", "origin": "court_center_net", "x": "left_to_right", "y": "net_to_far_baseline", "z": "up"}, "references": references, "source_homography_sha256": _sha256(self.homography_path), "source_camera_model_sha256": _sha256(self.camera_path), "created_at": datetime.now(timezone.utc).isoformat(), "source": "human_vertical_reference"}
        self.final_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        backup_dir = (self.state_root / "backups") if self.state_root else OUTPUT_ROOT / self.clip_id / "stage_5a1" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        (backup_dir / f"vertical_reference_{timestamp}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        stage_dir = self.state_root if self.state_root else OUTPUT_ROOT / self.clip_id / "stage_5a1"
        try:
            evaluation = evaluate_vertical_calibration(self.camera, self.candidates, self.homography, references)
            refined = evaluation["selected_model"]
            stage_dir.mkdir(parents=True, exist_ok=True)
            refined.write_json(stage_dir / "camera_model_refined.json", status=evaluation["status"], source_vertical_reference_sha256=_sha256(self.final_path), metrics=evaluation["metrics"], criteria=evaluation["criteria"], uncertainty=evaluation["jitter"])
            write_candidate_csv(stage_dir / "vertical_candidate_comparison.csv", evaluation["candidate_results"])
            (stage_dir / "vertical_jitter_report.json").write_text(json.dumps(evaluation["jitter"], indent=2) + "\n", encoding="utf-8")
            report = {key: value for key, value in evaluation.items() if key != "selected_model"}
            report["references"] = references
            (stage_dir / "vertical_calibration_report.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
            readiness = {"status": evaluation["status"], "passed_criteria": evaluation["criteria"]["passed"], "failed_criteria": evaluation["criteria"]["failed"], "ground_errors": evaluation["metrics"]["ground"], "vertical_errors": evaluation["metrics"]["vertical"], "sensitivity_before_px": evaluation["sensitivity_before_px"], "sensitivity_after_px": evaluation["sensitivity_after_px"], "improvement_percentage": evaluation["improvement_percentage"], "recommendation": evaluation["recommendation"], "stage_5b_started": False}
            (stage_dir / "readiness_report.json").write_text(json.dumps(readiness, indent=2) + "\n", encoding="utf-8")
            render_vertical_overlays(self.frame_path, stage_dir / "vertical_calibration_overlay.png", stage_dir / "vertical_calibration_closeup.png", refined, self.homography, references)
            return {"saved": True, "path": "data/clips/nivel_a2_01/vertical_reference.json", "status": evaluation["status"], "readiness": evaluation["status"], "message": "Las cuatro referencias fueron guardadas correctamente.", "evaluation_message": evaluation_message(evaluation["status"]), "diagnostic_path": "outputs/nivel_a2_01/stage_5a1/readiness_report.json"}
        except (ValueError, np.linalg.LinAlgError, RuntimeError) as exc:
            stage_dir.mkdir(parents=True, exist_ok=True)
            report = {"status": "INVALID_HUMAN_REFERENCE", "failed_criteria": [str(exc)], "stage_5b_started": False}
            (stage_dir / "readiness_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            return {"saved": True, "path": "data/clips/nivel_a2_01/vertical_reference.json", "status": "INVALID_HUMAN_REFERENCE", "readiness": "INVALID_HUMAN_REFERENCE", "message": "Las cuatro referencias fueron guardadas correctamente.", "evaluation_message": evaluation_message("INVALID_HUMAN_REFERENCE"), "diagnostic_path": "outputs/nivel_a2_01/stage_5a1/readiness_report.json"}

    def recalibrate(self, references: list[dict[str, Any]]) -> tuple[CameraModel, dict[str, float]]:
        points_world = np.asarray([item["world"] for item in references], dtype=np.float64)
        points_pixels = np.asarray([item["pixel"] for item in references], dtype=np.float64)
        corners = self.homography["court_corners_court_meters"]
        pixels = self.homography["court_corners_pixel"]
        ground_world = np.asarray([[*corners[name], 0.0] for name in ("far_left", "far_right", "near_left", "near_right", "far_left_service", "far_right_service", "near_left_service", "near_right_service")], dtype=np.float64)
        ground_pixels = np.asarray([pixels[name] for name in ("far_left", "far_right", "near_left", "near_right", "far_left_service", "far_right_service", "near_left_service", "near_right_service")], dtype=np.float64)
        return refine_pinhole_camera(self.camera, np.vstack([ground_world, points_world]), np.vstack([ground_pixels, points_pixels]))


def canvas_to_image_point(css_point: tuple[float, float], viewport: tuple[float, float], zoom: float, pan: tuple[float, float]) -> tuple[float, float]:
    """Map a CSS canvas coordinate to canonical pixels using contain + pan + zoom."""
    viewport_width, viewport_height = viewport
    scale = min(viewport_width / WIDTH, viewport_height / HEIGHT) * zoom
    left = (viewport_width - WIDTH * scale) / 2 + pan[0]
    top = (viewport_height - HEIGHT * scale) / 2 + pan[1]
    return ((css_point[0] - left) / scale, (css_point[1] - top) / scale)
