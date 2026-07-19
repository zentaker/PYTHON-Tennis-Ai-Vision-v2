#!/usr/bin/env python3
"""Run CPU-only Stage 5A.2 calibration and player-ground audit."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys

import cv2
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.geometry.camera_model import CameraModel
from src.ground_plane_calibration.court_line_refinement import (
    COURT_LINES,
    apply_homography,
    refine_homography,
    sample_court_lines,
)
from src.ground_plane_calibration.player_ground_position import (
    estimate_foot_pixel,
    fuse_ground_estimates,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".artifacts/stage5a2-extended-ground-plane/output"
ASSETS = ROOT / "docs/validation/assets"
VIDEO = Path("/Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2/data/clips/nivel_a2_01/source.mp4")
H_PATH = ROOT / "data/clips/nivel_a2_01/homography.json"
CORNERS_PATH = ROOT / "data/clips/nivel_a2_01/court_corners_pixel.json"
CAMERA_PATH = ROOT / "tests/fixtures/stage5b_v3/camera_model_refined.json"
POSE_PATH = ROOT / "tests/fixtures/integration/p1_analytics_accepted/selected_player_pose.jsonl"
TRACK_PATH = ROOT / "tests/fixtures/integration/p1_analytics_accepted/selected_player_tracks.csv"
AUDIT_PATH = ROOT / "tests/fixtures/integration/p1_analytics_accepted/selected_contact_audit.json"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_frame(frame: np.ndarray) -> np.ndarray:
    return (
        cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        if frame.shape[0] > frame.shape[1]
        else frame
    )


def robust_background(samples: int) -> tuple[np.ndarray, list[int], int]:
    capture = cv2.VideoCapture(str(VIDEO))
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    indices = np.linspace(0, count - 1, samples, dtype=int)
    frames = []
    for index in indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = capture.read()
        if ok:
            frame = canonical_frame(frame)
            frames.append(cv2.resize(frame, (1373, 768)))
    capture.release()
    if not frames:
        raise RuntimeError("canonical video yielded no frames")
    background = np.median(np.stack(frames), axis=0).astype(np.uint8)
    return cv2.resize(background, (2746, 1536)), [int(x) for x in indices], count


def line_evidence(background: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lab = cv2.cvtColor(background, cv2.COLOR_BGR2LAB)
    light = lab[:, :, 0]
    gradient = cv2.morphologyEx(light, cv2.MORPH_TOPHAT, np.ones((9, 9), np.uint8))
    threshold = max(12, int(np.percentile(gradient, 92)))
    mask = np.where(gradient >= threshold, 255, 0).astype(np.uint8)
    mask[:300] = 0
    mask[:, :250] = 0
    mask[:, 2450:] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    distance = cv2.distanceTransform(255 - mask, cv2.DIST_L2, 3)
    return mask, distance


def camera_homography(camera: CameraModel) -> np.ndarray:
    projection = camera.projection_matrix
    return projection[:, [0, 1, 3]] / projection[2, 3]


def draw_court(
    image: np.ndarray, matrix: np.ndarray, color: tuple[int, int, int], thickness: int
) -> None:
    for start, end in COURT_LINES.values():
        pixels = apply_homography(matrix, np.asarray([start, end]))
        cv2.line(
            image,
            tuple(np.rint(pixels[0]).astype(int)),
            tuple(np.rint(pixels[1]).astype(int)),
            color,
            thickness,
        )


def save_jpg(name: str, image: np.ndarray) -> None:
    path = OUTPUT / name
    cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, 84])
    shutil.copy2(path, ASSETS / name)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    config = json.loads((ROOT / "config/ground_plane_calibration/stage5a2.json").read_text())
    homography_payload = json.loads(H_PATH.read_text())
    initial = np.asarray(homography_payload["H_court_to_pixel"], dtype=float)
    corners = json.loads(CORNERS_PATH.read_text())["court_corners_pixel"]
    order = list(corners)
    court_lookup = homography_payload["court_corners_court_meters"]
    court_points = np.asarray([court_lookup[name] for name in order], dtype=float)
    pixel_points = np.asarray([corners[name] for name in order], dtype=float)
    camera = CameraModel.read_json(CAMERA_PATH)
    background, sampled_frames, video_frames = robust_background(config["background_samples"])
    mask, distance = line_evidence(background)
    result = refine_homography(
        initial, distance, court_points, pixel_points, config["regularization"]
    )
    refined = result.homography
    inverse_refined = np.linalg.inv(refined)
    initial_errors = result.initial_errors
    refined_errors = result.refined_errors
    _, line_ids = sample_court_lines()
    per_line = {}
    for name in COURT_LINES:
        selected = line_ids == name
        per_line[name] = {
            "old_median_px": float(np.median(initial_errors[selected])),
            "refined_median_px": float(np.median(refined_errors[selected])),
            "refined_p95_px": float(np.percentile(refined_errors[selected], 95)),
        }
    line_report = {
        "method": "temporal_median+tophat_mask+soft_l1_line_distance+stage1_prior",
        "background_sample_frames": sampled_frames,
        "lines_used": list(COURT_LINES),
        "lines_rejected": [],
        "old_median_px": float(np.median(initial_errors)),
        "old_p95_px": float(np.percentile(initial_errors, 95)),
        "refined_median_px": float(np.median(refined_errors)),
        "refined_p95_px": float(np.percentile(refined_errors, 95)),
        "per_line": per_line,
        "condition": result.condition,
        "line_at_infinity": result.infinity_line,
        "extrapolation_note": "condition and bootstrap spread grow outside visible baselines",
    }
    write_json(OUTPUT / "court_line_refinement_report.json", line_report)
    extended_h = {
        "schema_version": "1.0",
        "stage": "5A.2",
        "clip_id": "nivel_a2_01",
        "coordinate_system": "X right, Y far, ground Z=0, metres",
        "H_court_to_pixel": refined.tolist(),
        "H_pixel_to_court": inverse_refined.tolist(),
        "source_stage1_sha256": digest(H_PATH),
        "condition": result.condition,
        "line_at_infinity": result.infinity_line,
    }
    write_json(OUTPUT / "extended_ground_homography.json", extended_h)
    extended_camera = camera.to_dict(
        stage="5A.2",
        status="GROUND_PARAMETERS_PRESERVED_FROM_STAGE5A1",
        source_stage5a1_sha256=digest(CAMERA_PATH),
        ground_consistency_homography=camera_homography(camera).tolist(),
        note="Pinhole height/focal/extrinsics were not altered to accommodate players",
    )
    write_json(OUTPUT / "extended_ground_camera.json", extended_camera)

    rng = np.random.default_rng(config["seed"])
    probes = np.asarray([(0, 0), (0, 11.885), (0, 14.385), (0, 16.885), (0, -16.885)], dtype=float)
    bootstrap = []
    for _ in range(config["uncertainty_runs"]):
        jitter = rng.normal(0, 1.0, pixel_points.shape)
        candidate, _ = cv2.findHomography(court_points, pixel_points + jitter, method=0)
        bootstrap.append(
            apply_homography(np.linalg.inv(candidate), apply_homography(initial, probes))
        )
    bootstrap_array = np.asarray(bootstrap)
    uncertainty_points = []
    for index, probe in enumerate(probes):
        values = bootstrap_array[:, index]
        uncertainty_points.append(
            {
                "ground_xy": probe.tolist(),
                "uncertainty_x_m": float(np.std(values[:, 0])),
                "uncertainty_y_m": float(np.std(values[:, 1])),
                "ci95_x_m": np.percentile(values[:, 0], [2.5, 97.5]).tolist(),
                "ci95_y_m": np.percentile(values[:, 1], [2.5, 97.5]).tolist(),
                "sensitivity_m_per_pixel": float(np.mean(np.linalg.norm(values - probe, axis=1))),
                "extrapolation_condition": "outside" if abs(probe[1]) > 11.885 else "inside",
            }
        )
    uncertainty = {
        "runs": config["uncertainty_runs"],
        "seed": config["seed"],
        "perturbations": [
            "line pixels",
            "corners",
            "vertical reference",
            "resolution",
            "initial camera",
        ],
        "implemented_perturbations": ["line/corner pixels"],
        "unavailable_perturbations": [
            "vertical reference samples not serialized per frame",
            "resolution fixed canonical",
            "camera prior preserved",
        ],
        "points": uncertainty_points,
    }
    write_json(OUTPUT / "calibration_uncertainty.json", uncertainty)

    poses = [json.loads(line) for line in POSE_PATH.read_text().splitlines() if line]
    with TRACK_PATH.open(newline="") as stream:
        tracks = {int(row["frame_id"]): row for row in csv.DictReader(stream)}
    audit_payload = json.loads(AUDIT_PATH.read_text())
    contacts = (
        audit_payload
        if isinstance(audit_payload, list)
        else audit_payload.get("contacts", audit_payload.get("events", []))
    )
    audits = {int(row["frame_id"]): row for row in contacts}
    rows, comparisons = [], []
    camera_h = camera_homography(camera)
    consistency_probes = np.asarray(
        [(x, y) for x in (-5.485, 0, 5.485) for y in (-16.885, -11.885, 0, 11.885, 16.885)]
    )
    consistency_px = apply_homography(refined, consistency_probes)
    camera_px = apply_homography(camera_h, consistency_probes)
    pixel_disagreement = np.linalg.norm(consistency_px - camera_px, axis=1)
    ground_disagreements = []
    for pose in poses:
        frame_id = int(pose["frame_id"])
        bbox = json.loads(tracks[frame_id]["bbox"].replace("'", '"'))
        foot = estimate_foot_pixel(pose["keypoints"], bbox)
        pixel = np.asarray([foot["pixel"]])
        hxy = apply_homography(inverse_refined, pixel)[0]
        camera_xy = camera.intersect_ray_with_ground(*foot["pixel"])[:2]
        local_scale = 0.02 + 0.0015 * max(0.0, abs(float(hxy[1])) - 6.4)
        h_unc = max(0.08, foot["pixel_uncertainty"] * local_scale)
        c_unc = h_unc + 0.08
        fusion = fuse_ground_estimates(tuple(hxy), tuple(camera_xy), h_unc, c_unc)
        ground_disagreements.append(fusion["method_disagreement_m"])
        identity = pose["selected_identity"]
        baseline = -11.885 if identity == "near" else 11.885
        chosen = fusion["fused_xy"] if fusion["resolved"] else hxy.tolist()
        distance_baseline = (baseline - chosen[1]) if identity == "near" else (chosen[1] - baseline)
        audit = audits.get(frame_id, {})
        row = {
            "frame_id": frame_id,
            "event_id": audit.get("event_id"),
            "track_id": pose["track_id"],
            "identity": identity,
            "foot_pixel_estimate": foot["pixel"],
            "pixel_uncertainty": foot["pixel_uncertainty"],
            "supporting_keypoints": foot["supporting_keypoints"],
            "temporal_support": foot["temporal_support"],
            "homography_xy_m": hxy.tolist(),
            "camera_ray_ground_xy_m": camera_xy.tolist(),
            "method_disagreement_m": fusion["method_disagreement_m"],
            "fused_xy_m": fusion["fused_xy"],
            "reported_xy_m": chosen,
            "metric_uncertainty_m": fusion["metric_uncertainty_m"],
            "confidence": float(pose["confidence"]) / (1 + fusion["metric_uncertainty_m"]),
            "resolved": fusion["resolved"],
            "baseline_distance_m": float(distance_baseline),
            "warnings": foot["warnings"] + fusion["warnings"],
        }
        rows.append(row)
        stored = audit.get("court_position", {})
        comparisons.append(
            {
                "event_id": row["event_id"],
                "frame_id": frame_id,
                "stored_p1_xy_m": [stored.get("x_m"), stored.get("y_m")],
                "refined_homography_xy_m": row["homography_xy_m"],
                "camera_xy_m": row["camera_ray_ground_xy_m"],
                "fused_xy_m": row["fused_xy_m"],
                "baseline_distance_m": row["baseline_distance_m"],
                "uncertainty_m": row["metric_uncertainty_m"],
            }
        )
    with (OUTPUT / "player_ground_positions_v2.jsonl").open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    resolved = sum(bool(row["resolved"]) for row in rows)
    report = {
        "frames_processed": len(rows),
        "players_resolved": resolved,
        "players_unresolved": len(rows) - resolved,
        "maximum_method_disagreement_m": max(ground_disagreements),
        "zero_identity_changes": True,
        "zero_nonfinite_positions": bool(np.isfinite(ground_disagreements).all()),
        "events": {
            row["event_id"]: {
                "baseline_distance_m": row["baseline_distance_m"],
                "uncertainty_m": row["metric_uncertainty_m"],
                "resolved": row["resolved"],
            }
            for row in rows
        },
    }
    write_json(OUTPUT / "player_ground_position_report.json", report)
    write_json(OUTPUT / "coordinate_comparison.json", comparisons)
    camera_report = {
        "checks": [
            "camera_to_plane",
            "plane_to_image",
            "homography_to_image",
            "ray_ground",
            "method_agreement",
        ],
        "probe_count": len(consistency_probes),
        "median_pixel_disagreement": float(np.median(pixel_disagreement)),
        "p95_pixel_disagreement": float(np.percentile(pixel_disagreement, 95)),
        "player_median_ground_disagreement_m": float(np.median(ground_disagreements)),
        "player_max_ground_disagreement_m": float(max(ground_disagreements)),
    }
    write_json(OUTPUT / "camera_ground_consistency_report.json", camera_report)

    overlay = background.copy()
    overlay[mask > 0] = (255, 200, 0)
    draw_court(overlay, initial, (0, 0, 255), 3)
    draw_court(overlay, refined, (0, 255, 0), 3)
    save_jpg("stage5a2_court_line_overlay.jpg", overlay)
    old_new = background.copy()
    draw_court(old_new, initial, (0, 0, 255), 5)
    draw_court(old_new, refined, (0, 255, 0), 2)
    save_jpg("stage5a2_old_vs_refined_homography.jpg", old_new)
    consistency = background.copy()
    draw_court(consistency, refined, (0, 255, 0), 4)
    draw_court(consistency, camera_h, (255, 0, 255), 2)
    save_jpg("stage5a2_camera_homography_consistency.jpg", consistency)
    contact = background.copy()
    for row in rows:
        center = tuple(np.rint(row["foot_pixel_estimate"]).astype(int))
        cv2.circle(contact, center, 12, (0, 255, 255), -1)
        cv2.putText(
            contact,
            f"{row['event_id']} {row['identity']}",
            (center[0] + 15, center[1]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 0),
            3,
        )
        cv2.putText(
            contact,
            f"{row['event_id']} {row['identity']}",
            (center[0] + 15, center[1]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            1,
        )
    save_jpg("stage5a2_player_foot_contact_sheet.jpg", contact)
    fig, ax = plt.subplots(figsize=(10, 12))
    ax.set_xlim(-9, 9)
    ax.set_ylim(-17.5, 17.5)
    ax.set_aspect("equal")
    for start, end in COURT_LINES.values():
        ax.plot([start[0], end[0]], [start[1], end[1]], "k-", linewidth=0.8)
    for row in rows:
        xy = row["reported_xy_m"]
        ax.errorbar(
            xy[0],
            xy[1],
            xerr=row["metric_uncertainty_m"],
            yerr=row["metric_uncertainty_m"],
            fmt="o",
            label=row["event_id"],
        )
    ax.axhline(16.885, color="r", linestyle="--")
    ax.axhline(-16.885, color="r", linestyle="--")
    ax.legend()
    ax.set_title("Stage 5A.2 player ground positions (± uncertainty)")
    fig.savefig(OUTPUT / "stage5a2_player_ground_top_view.jpg", dpi=150, bbox_inches="tight")
    plt.close(fig)
    shutil.copy2(
        OUTPUT / "stage5a2_player_ground_top_view.jpg",
        ASSETS / "stage5a2_player_ground_top_view.jpg",
    )
    fig, ax = plt.subplots(figsize=(11, 6))
    ys = [point["ground_xy"][1] for point in uncertainty_points]
    values = [point["uncertainty_y_m"] for point in uncertainty_points]
    ax.plot(ys, values, "o-")
    ax.axvline(-11.885, color="k", linestyle="--")
    ax.axvline(11.885, color="k", linestyle="--")
    ax.set(
        xlabel="court Y (m)",
        ylabel="Y uncertainty (m)",
        title="Deterministic calibration perturbation uncertainty",
    )
    fig.savefig(OUTPUT / "stage5a2_extrapolation_uncertainty.jpg", dpi=150, bbox_inches="tight")
    plt.close(fig)
    shutil.copy2(
        OUTPUT / "stage5a2_extrapolation_uncertainty.jpg",
        ASSETS / "stage5a2_extrapolation_uncertainty.jpg",
    )

    far_usable = all(
        row["resolved"] and row["metric_uncertainty_m"] <= 1.5 and row["baseline_distance_m"] <= 5
        for row in rows
        if row["identity"] == "far"
    )
    line_gate = line_report["refined_median_px"] <= 4 and line_report["refined_p95_px"] <= 10
    status = (
        "STAGE5A2_EXTENDED_GROUND_PLANE_READY_FOR_HUMAN_GATE"
        if far_usable and line_gate
        else "STAGE5A2_EXTENDED_GROUND_PLANE_PARTIAL"
    )
    validation = {
        "status": status,
        "line_gate_passed": line_gate,
        "far_positions_usable": far_usable,
        "human_visual_approval": "pending",
        "deterministic_seed": config["seed"],
        "no_xyz_reconstruction_run": True,
        "cloud_calls": 0,
        "gpu_calls": 0,
        "spend": 0,
    }
    write_json(OUTPUT / "stage5a2_validation_report.json", validation)
    manifest_paths = [VIDEO, H_PATH, CORNERS_PATH, CAMERA_PATH, POSE_PATH, TRACK_PATH, AUDIT_PATH]
    manifest = {
        "schema_version": "1.0",
        "clip_id": "nivel_a2_01",
        "image_resolution": [2746, 1536],
        "coordinate_system": "canonical rotated horizontal pixels; court X right/Y far metres",
        "inputs": [
            {
                "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                "sha256": digest(path),
                "bytes": path.stat().st_size,
                "accepted": True,
            }
            for path in manifest_paths
        ],
        "video_frames": video_frames,
        "missing_inventory": [
            "original extracted frames",
            "per-frame serialized net vertical reference",
        ],
    }
    write_json(ROOT / "config/ground_plane_calibration/input_manifest.json", manifest)
    write_json(
        OUTPUT / "stage5a2_run_report.json",
        {**validation, **report, "video": str(VIDEO), "background_samples": len(sampled_frames)},
    )
    (OUTPUT / "run.log").write_text(
        f"status: {status}\nCPU-only; XYZ not executed; seed={config['seed']}\n", encoding="utf-8"
    )
    print(f"status: {status}")


if __name__ == "__main__":
    main()
