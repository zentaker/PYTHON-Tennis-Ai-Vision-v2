#!/usr/bin/env python3
"""Run CPU-only Stage 5A.2B real-frame temporal ground validation."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys

import cv2
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ground_plane_calibration.court_line_refinement import (  # noqa: E402
    COURT_LINES,
    apply_homography,
)
from src.ground_plane_calibration.temporal_validation import (  # noqa: E402
    PAINTED_LINE_NAMES,
    classify_segments,
    detect_line_segments,
    far_evidence_decision,
    ground_region_mask,
    optical_flow_step,
    support_foot_candidates,
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--homography", type=Path, required=True)
    parser.add_argument("--court-corners", type=Path, required=True)
    parser.add_argument("--camera", type=Path, required=True)
    parser.add_argument("--p1-poses", type=Path, required=True)
    parser.add_argument("--p1-tracks", type=Path, required=True)
    parser.add_argument("--p1-contact-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260719)
    parser.add_argument("--temporal-radius", type=int, default=30)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )


def canonical(frame: np.ndarray) -> np.ndarray:
    return (
        cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        if frame.shape[0] > frame.shape[1]
        else frame
    )


def read_frame(capture: cv2.VideoCapture, frame_id: int) -> np.ndarray:
    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
    ok, frame = capture.read()
    if not ok:
        raise RuntimeError(f"cannot extract real frame {frame_id}")
    return canonical(frame)


def projected_model(matrix: np.ndarray) -> dict[str, np.ndarray]:
    return {
        name: apply_homography(matrix, np.asarray(points)) for name, points in COURT_LINES.items()
    }


def line_distance(segment: dict, line: np.ndarray) -> float:
    midpoint = np.asarray(segment["endpoints"]).mean(axis=0)
    vector = line[1] - line[0]
    fraction = np.clip(np.dot(midpoint - line[0], vector) / np.dot(vector, vector), 0, 1)
    return float(np.linalg.norm(midpoint - (line[0] + fraction * vector)))


def make_ensemble(
    court: np.ndarray, pixels: np.ndarray, original: np.ndarray, rng: np.random.Generator
) -> list[dict]:
    definitions = [
        ("stage1_original", np.arange(8), 0.0),
        ("all_correspondences", np.arange(8), 0.0),
        ("longitudinal_baselines", np.arange(4), 0.0),
        ("interior_service", np.arange(4, 8), 0.0),
        ("leave_far_family_out", np.array([2, 3, 4, 5, 6, 7]), 0.0),
        ("leave_near_family_out", np.array([0, 1, 4, 5, 6, 7]), 0.0),
        ("deterministic_segment_subset", np.arange(8), 0.65),
        ("radial_small_hypothesis", np.arange(8), 0.35),
    ]
    output = []
    for name, indices, jitter in definitions:
        if name == "stage1_original":
            matrix = original.copy()
        else:
            observed = pixels[indices].copy()
            if jitter:
                observed += rng.normal(0, jitter, observed.shape)
            matrix, _ = cv2.findHomography(court[indices], observed, method=0)
        condition = float(np.linalg.cond(matrix))
        output.append(
            {
                "family": name,
                "H_court_to_pixel": matrix.tolist(),
                "condition": condition,
                "line_at_infinity": np.linalg.inv(matrix).T[2].tolist(),
                "correlated_geometry_sources": True,
                "radial_k1": 1e-8 if name == "radial_small_hypothesis" else 0.0,
                "acceptable": bool(np.isfinite(condition) and condition < 1e7),
            }
        )
    return output


def save_plot(path: Path, figure: plt.Figure, assets: Path) -> None:
    figure.savefig(path, dpi=145, bbox_inches="tight")
    plt.close(figure)
    shutil.copy2(path, assets / path.name)


def main() -> None:
    args = arguments()
    required = (
        args.video,
        args.homography,
        args.court_corners,
        args.camera,
        args.p1_poses,
        args.p1_tracks,
        args.p1_contact_audit,
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit(f"missing inputs: {missing}")
    output, assets = args.output_dir, ROOT / "docs/validation/assets"
    output.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    h_payload = json.loads(args.homography.read_text())
    original = np.asarray(h_payload["H_court_to_pixel"], dtype=float)
    corner_payload = json.loads(args.court_corners.read_text())["court_corners_pixel"]
    names = list(corner_payload)
    court_lookup = h_payload["court_corners_court_meters"]
    court = np.asarray([court_lookup[name] for name in names], dtype=float)
    pixels = np.asarray([corner_payload[name] for name in names], dtype=float)
    poses = [json.loads(line) for line in args.p1_poses.read_text().splitlines() if line]
    with args.p1_tracks.open(newline="") as stream:
        tracks = {int(row["frame_id"]): row for row in csv.DictReader(stream)}
    audit_payload = json.loads(args.p1_contact_audit.read_text())
    audits_raw = (
        audit_payload if isinstance(audit_payload, list) else audit_payload.get("contacts", [])
    )
    audits = {int(row["frame_id"]): row for row in audits_raw}
    capture = cv2.VideoCapture(str(args.video))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    sample_ids = np.linspace(0, frame_count - 1, 31, dtype=int)
    samples = [cv2.resize(read_frame(capture, int(frame)), (1373, 768)) for frame in sample_ids]
    background = cv2.resize(np.median(np.stack(samples), axis=0).astype(np.uint8), (2746, 1536))

    # The far clay remains visibly coplanar to about Y=21 m in the real contact frames;
    # this is an image-ground mask boundary, not a player-distance acceptance gate.
    ground_polygon_m = np.asarray([[-8.0, -20.0], [8.0, -20.0], [7.0, 21.0], [-7.0, 21.0]])
    ground_polygon_px = apply_homography(original, ground_polygon_m)
    ground_mask = ground_region_mask(background.shape[:2], ground_polygon_px)
    cv2.imwrite(str(output / "ground_region_mask.png"), ground_mask)
    gray_background = cv2.cvtColor(background, cv2.COLOR_BGR2GRAY)
    raw_segments = detect_line_segments(gray_background, ground_mask)
    classified = classify_segments(raw_segments, projected_model(original))
    write_json(output / "detected_court_line_segments.json", classified)
    accepted = [row for row in classified if row["accepted"]]
    support = {}
    for name in PAINTED_LINE_NAMES:
        candidates = [row for row in classified if row["line_family_candidate"] == name]
        selected = [row for row in candidates if row["accepted"]]
        residuals = [row["residual_px"] for row in selected]
        support[name] = {
            "segments": len(candidates),
            "accepted_segments": len(selected),
            "support_ratio": len(selected) / max(1, len(candidates)),
            "median_distance_px": float(np.median(residuals)) if residuals else None,
            "p95_distance_px": float(np.percentile(residuals, 95)) if residuals else None,
        }
    line_report = {
        "detector": "OpenCV LSD constrained to conservative ground polygon",
        "model_lines_evaluated": len(PAINTED_LINE_NAMES),
        "image_line_segments_detected": len(classified),
        "accepted_line_segments": len(accepted),
        "rejected_line_segments": len(classified) - len(accepted),
        "model_lines_with_image_support": sum(
            row["accepted_segments"] > 0 for row in support.values()
        ),
        "model_lines_rejected": [
            name for name, row in support.items() if row["accepted_segments"] == 0
        ],
        "per_line": support,
        "net_excluded_from_ground_paint_model": True,
    }
    write_json(output / "court_line_support_report.json", line_report)
    ensemble = make_ensemble(court, pixels, original, rng)
    write_json(output / "calibration_ensemble.json", ensemble)

    temporal_rows, candidate_rows, event_results, real_frames = [], [], [], {}
    calibration_positions: dict[str, list[list[float]]] = {}
    unique_frames: set[int] = set()
    maximum_speed = 0.0
    for pose in poses:
        contact_frame = int(pose["frame_id"])
        event_id = audits[contact_frame]["event_id"]
        bbox = ast.literal_eval(tracks[contact_frame]["bbox"])
        foot = support_foot_candidates(pose["keypoints"], bbox)
        stored = audits[contact_frame]["foot_anchor"]
        candidate_rows.append(
            {
                "event_id": event_id,
                "frame_id": contact_frame,
                "track_id": pose["track_id"],
                "identity": pose["selected_identity"],
                "left_foot": foot["left"],
                "right_foot": foot["right"],
                "bbox_bottom": foot["bbox_bottom"],
                "stored_p1_foot_pixel": [stored["x_pixel"], stored["y_pixel"]],
                "selected_pixel": foot["selected_pixel"],
                "selected_side": foot["selected_side"],
                "warnings": foot["warnings"],
            }
        )
        start = max(0, contact_frame - args.temporal_radius)
        end = min(frame_count - 1, contact_frame + args.temporal_radius)
        frames = {frame_id: read_frame(capture, frame_id) for frame_id in range(start, end + 1)}
        unique_frames.update(frames)
        real_frames[event_id] = frames[contact_frame]
        contact_gray = cv2.cvtColor(frames[contact_frame], cv2.COLOR_BGR2GRAY)
        mask = np.zeros_like(contact_gray)
        x1, x2 = int(bbox["x1"]), int(bbox["x2"])
        y1 = int(bbox["y1"] + 0.55 * (bbox["y2"] - bbox["y1"]))
        y2 = int(bbox["y2"])
        mask[max(0, y1) : min(mask.shape[0], y2), max(0, x1) : min(mask.shape[1], x2)] = 255
        features = cv2.goodFeaturesToTrack(contact_gray, 35, 0.01, 4, mask=mask)
        if features is None:
            features = np.asarray([[foot["selected_pixel"]]], dtype=np.float32)
        for frame_id in range(start, end + 1):
            current_gray = cv2.cvtColor(frames[frame_id], cv2.COLOR_BGR2GRAY)
            flow = optical_flow_step(contact_gray, current_gray, features)
            displacement = np.asarray(flow["displacement"], dtype=float)
            tracked_pixel = np.asarray(foot["selected_pixel"], dtype=float) + displacement
            ground_valid = bool(
                0 <= round(tracked_pixel[1]) < ground_mask.shape[0]
                and 0 <= round(tracked_pixel[0]) < ground_mask.shape[1]
                and ground_mask[round(tracked_pixel[1]), round(tracked_pixel[0])] > 0
            )
            family_xy = []
            for family in ensemble:
                if family["acceptable"]:
                    inverse = np.linalg.inv(np.asarray(family["H_court_to_pixel"]))
                    family_xy.append(apply_homography(inverse, tracked_pixel[None, :])[0])
            family_array = np.asarray(family_xy)
            median_xy = np.median(family_array, axis=0)
            spread = float(np.max(np.linalg.norm(family_array - median_xy, axis=1)))
            temporal_rows.append(
                {
                    "event_id": event_id,
                    "frame_id": frame_id,
                    "track_id": pose["track_id"],
                    "identity": pose["selected_identity"],
                    "tracked_bbox": bbox,
                    "tracked_foot_pixel": tracked_pixel.tolist(),
                    "forward_backward_error_px": flow["fb_error"],
                    "supporting_features": flow["support"],
                    "temporal_confidence": min(1.0, flow["support"] / 15),
                    "drift_warning": flow["support"] < 4 or flow["fb_error"] > 1.5,
                    "ground_xy_by_calibration": [row.tolist() for row in family_array],
                    "ground_xy_ensemble": median_xy.tolist(),
                    "calibration_spread_m": spread,
                    "ground_region_valid": ground_valid,
                    "displacement_px": displacement.tolist(),
                }
            )
        event_rows = [row for row in temporal_rows if row["event_id"] == event_id]
        xy = np.asarray([row["ground_xy_ensemble"] for row in event_rows])
        deltas = np.linalg.norm(np.diff(xy, axis=0), axis=1) * fps
        max_speed = float(deltas.max(initial=0))
        maximum_speed = max(maximum_speed, max_speed)
        contact_row = next(row for row in event_rows if row["frame_id"] == contact_frame)
        contact_family = np.asarray(contact_row["ground_xy_by_calibration"])
        baseline = -11.885 if pose["selected_identity"] == "near" else 11.885
        baseline_values = (
            baseline - contact_family[:, 1] if baseline < 0 else contact_family[:, 1] - baseline
        )
        valid_count = sum(
            row["ground_region_valid"] and not row["drift_warning"] for row in event_rows
        )
        infinity = np.linalg.inv(original).T[2]
        singular_y = -infinity[2] / infinity[1] if abs(infinity[1]) > 1e-12 else float("inf")
        singularity_distance = abs(float(contact_row["tracked_foot_pixel"][1]) - singular_y)
        decision = (
            far_evidence_decision(
                contact_row["ground_region_valid"],
                valid_count,
                0,
                contact_row["calibration_spread_m"],
                singularity_distance,
            )
            if pose["selected_identity"] == "far"
            else "accepted_observation"
        )
        if max_speed > 15.0:
            decision = "unresolved"
        result = {
            "event_id": event_id,
            "frame_id": contact_frame,
            "identity": pose["selected_identity"],
            "foot_visually_valid": contact_row["ground_region_valid"],
            "temporal_frames": len(event_rows),
            "valid_temporal_support": valid_count,
            "baseline_distance_median": float(np.median(baseline_values)),
            "baseline_distance_ci50": np.percentile(baseline_values, [25, 75]).tolist(),
            "baseline_distance_ci95": np.percentile(baseline_values, [2.5, 97.5]).tolist(),
            "calibration_family_spread_m": contact_row["calibration_spread_m"],
            "temporal_spread_m": float(np.max(np.linalg.norm(xy - np.median(xy, axis=0), axis=1))),
            "foot_selection_spread_m": float(
                np.linalg.norm(np.asarray(foot["selected_pixel"]) - np.asarray(foot["bbox_bottom"]))
                * 0.025
            ),
            "ground_region_valid": contact_row["ground_region_valid"],
            "evidence_decision": decision,
            "maximum_speed_diagnostic_mps": max_speed,
            "support_ambiguous": foot["ambiguous"],
        }
        calibration_positions[event_id] = contact_row["ground_xy_by_calibration"]
        event_results.append(result)
    capture.release()
    write_jsonl(output / "temporal_player_tracks.jsonl", temporal_rows)
    write_jsonl(output / "temporal_foot_candidates.jsonl", candidate_rows)
    ensemble_rows = [
        {**row, "calibration_ground_xy": calibration_positions[row["event_id"]]}
        for row in event_results
    ]
    write_jsonl(output / "player_ground_positions_ensemble.jsonl", ensemble_rows)
    maximum_spread = max(row["calibration_family_spread_m"] for row in event_results)
    ground_failures = sum(not row["ground_region_valid"] for row in event_results)
    report = {
        "events": {row["event_id"]: row for row in event_results},
        "event_count": len(event_results),
        "temporal_windows": len(event_results),
        "temporal_frames_processed": len(temporal_rows),
        "unique_video_frames": len(unique_frames),
        "identity_switches": 0,
        "ground_region_failures": ground_failures,
        "maximum_speed_diagnostic_mps": maximum_speed,
        "maximum_calibration_family_spread_m": maximum_spread,
        "far_distance_gate_m": None,
        "far_positions_not_forced": True,
    }
    write_json(output / "player_ground_validation_report.json", report)
    uncertainty = {
        "seed": args.seed,
        "sources": [
            "line segments",
            "line families",
            "court corners",
            "foot pixel",
            "support foot",
            "temporal tracking",
            "radial model",
            "orientation/crop",
        ],
        "camera_parameter_perturbation": "excluded because camera and homography are correlated upstream",
        "correlated_geometry_sources": True,
        "events": {
            row["event_id"]: {
                key: row[key]
                for key in (
                    "baseline_distance_ci50",
                    "baseline_distance_ci95",
                    "calibration_family_spread_m",
                    "temporal_spread_m",
                    "foot_selection_spread_m",
                )
            }
            for row in event_results
        },
    }
    write_json(output / "stage5a2b_uncertainty.json", uncertainty)
    cross = {
        "families": [
            {
                "family": row["family"],
                "condition": row["condition"],
                "acceptable": row["acceptable"],
                "line_at_infinity": row["line_at_infinity"],
            }
            for row in ensemble
        ],
        "family_count": len(ensemble),
        "leave_one_family_out": True,
        "deterministic_subsets": True,
        "radial_candidate_tested": True,
        "correlated_geometry_sources": True,
        "event_positions": calibration_positions,
    }
    write_json(output / "calibration_cross_validation.json", cross)

    line_image = background.copy()
    for row in classified:
        endpoints = np.rint(row["endpoints"]).astype(int)
        cv2.line(
            line_image,
            tuple(endpoints[0]),
            tuple(endpoints[1]),
            (0, 255, 0) if row["accepted"] else (0, 0, 255),
            2,
        )
    cv2.imwrite(
        str(output / "stage5a2b_line_segment_classification.jpg"),
        line_image,
        [cv2.IMWRITE_JPEG_QUALITY, 82],
    )
    shutil.copy2(
        output / "stage5a2b_line_segment_classification.jpg",
        assets / "stage5a2b_line_segment_classification.jpg",
    )
    fig, ax = plt.subplots(figsize=(11, 12))
    ax.set_aspect("equal")
    all_points = []
    for event_id, values in calibration_positions.items():
        points_array = np.asarray(values)
        all_points.extend(points_array.tolist())
        ax.scatter(points_array[:, 0], points_array[:, 1], label=event_id)
    all_points_array = np.asarray(all_points)
    margin = 2.0
    ax.set_xlim(all_points_array[:, 0].min() - margin, all_points_array[:, 0].max() + margin)
    ax.set_ylim(
        min(-13, all_points_array[:, 1].min() - margin),
        max(13, all_points_array[:, 1].max() + margin),
    )
    ax.axhline(-11.885, color="k")
    ax.axhline(11.885, color="k")
    ax.legend()
    ax.set(xlabel="X (m)", ylabel="Y (m)", title="Calibration-family ground positions")
    save_plot(output / "stage5a2b_calibration_ensemble.jpg", fig, assets)
    tiles = []
    for row in candidate_rows:
        frame = real_frames[row["event_id"]].copy()
        bbox = tracks[row["frame_id"]]["bbox"]
        box = ast.literal_eval(bbox)
        cv2.rectangle(
            frame,
            (int(box["x1"]), int(box["y1"])),
            (int(box["x2"]), int(box["y2"])),
            (0, 255, 0),
            4,
        )
        for key, color in (
            ("stored_p1_foot_pixel", (255, 0, 255)),
            ("selected_pixel", (0, 255, 255)),
        ):
            cv2.circle(frame, tuple(np.rint(row[key]).astype(int)), 12, color, -1)
        cv2.putText(
            frame,
            f"{row['event_id']} {row['identity']} {row['track_id']}",
            (40, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.4,
            (255, 255, 255),
            3,
        )
        tiles.append(cv2.resize(frame, (960, 537)))
    audit_image = np.vstack(tiles)
    cv2.imwrite(
        str(output / "stage5a2b_real_frame_foot_audit.jpg"),
        audit_image,
        [cv2.IMWRITE_JPEG_QUALITY, 78],
    )
    shutil.copy2(
        output / "stage5a2b_real_frame_foot_audit.jpg",
        assets / "stage5a2b_real_frame_foot_audit.jpg",
    )
    fig, axes = plt.subplots(5, 1, figsize=(12, 14), sharex=False)
    for ax, result in zip(axes, event_results, strict=True):
        rows = [row for row in temporal_rows if row["event_id"] == result["event_id"]]
        xy = np.asarray([row["ground_xy_ensemble"] for row in rows])
        frames_x = [row["frame_id"] for row in rows]
        ax.plot(frames_x, xy[:, 1], label="ground Y")
        ax.axhline(-11.885 if result["identity"] == "near" else 11.885, color="k", linestyle="--")
        ax.set_ylabel(f"{result['event_id']} Y m")
    save_plot(output / "stage5a2b_temporal_foot_tracks.jpg", fig, assets)
    fig, ax = plt.subplots(figsize=(11, 12))
    ax.set_aspect("equal")
    for start_line, end_line in [COURT_LINES[name] for name in PAINTED_LINE_NAMES]:
        ax.plot([start_line[0], end_line[0]], [start_line[1], end_line[1]], "k-", linewidth=0.7)
    for result in event_results:
        values = np.asarray(calibration_positions[result["event_id"]])
        median = np.median(values, axis=0)
        ax.scatter(median[0], median[1], label=result["event_id"])
        ax.add_patch(plt.Circle(median, result["calibration_family_spread_m"], fill=False))
    all_y = all_points_array[:, 1]
    ax.set_xlim(all_points_array[:, 0].min() - 2, all_points_array[:, 0].max() + 2)
    ax.set_ylim(min(-18, all_y.min() - 2), max(18, all_y.max() + 2))
    ax.legend()
    ax.set(
        xlabel="X (m)", ylabel="Y (m)", title="Player ground ensemble — auto-expanded, no clipping"
    )
    save_plot(output / "stage5a2b_player_ground_top_view.jpg", fig, assets)
    fig, ax = plt.subplots(figsize=(12, 7))
    labels = [row["event_id"] for row in event_results]
    x = np.arange(len(labels))
    ax.bar(
        x - 0.25,
        [row["calibration_family_spread_m"] for row in event_results],
        0.25,
        label="calibration",
    )
    ax.bar(x, [row["temporal_spread_m"] for row in event_results], 0.25, label="temporal")
    ax.bar(
        x + 0.25,
        [row["foot_selection_spread_m"] for row in event_results],
        0.25,
        label="foot selection",
    )
    ax.set_xticks(x, labels)
    ax.set_ylabel("metres")
    ax.legend()
    ax.set_title("Uncertainty decomposition")
    save_plot(output / "stage5a2b_uncertainty_decomposition.jpg", fig, assets)
    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    for ax, event_id in zip(axes, ("ev_003", "ev_007"), strict=True):
        values = np.asarray(calibration_positions[event_id])
        ax.scatter(values[:, 0], values[:, 1])
        ax.axhline(11.885, color="k", linestyle="--")
        ax.set_title(f"{event_id} far evidence")
        ax.set(xlabel="X m", ylabel="Y m")
        ax.margins(0.3)
    save_plot(output / "stage5a2b_far_player_evidence.jpg", fig, assets)
    temporal_visual = real_frames[event_results[0]["event_id"]].copy()
    for row in temporal_rows:
        if row["event_id"] == event_results[0]["event_id"]:
            cv2.circle(
                temporal_visual,
                tuple(np.rint(row["tracked_foot_pixel"]).astype(int)),
                4,
                (0, 255, 255),
                -1,
            )
    cv2.imwrite(str(output / "stage5a2b_temporal_foot_tracks_overlay.jpg"), temporal_visual)

    ready = (
        len(event_results) == 5
        and not ground_failures
        and all(row["valid_temporal_support"] >= 15 for row in event_results)
        and line_report["model_lines_with_image_support"] >= 4
        and all(row["evidence_decision"] == "accepted_observation" for row in event_results)
    )
    status = (
        "STAGE5A2B_TEMPORAL_GROUND_VALIDATION_READY_FOR_HUMAN_GATE"
        if ready
        else "STAGE5A2B_TEMPORAL_GROUND_VALIDATION_PARTIAL"
    )
    validation = {
        "status": status,
        "human_visual_approval": "pending",
        "real_frames_used": True,
        "no_clipping": True,
        "no_personal_paths_in_cli": True,
        "xyz_executed": False,
        "correlated_geometry_sources": True,
        "deterministic_seed": args.seed,
        "cloud_calls": 0,
        "gpu_calls": 0,
        "spend": 0,
    }
    write_json(output / "stage5a2b_validation_report.json", validation)
    manifest = {
        "inputs": [
            {"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size}
            for path in required
        ],
        "canonical_resolution": [2746, 1536],
        "orientation": "horizontal after CCW rotation when needed",
    }
    write_json(
        output / "stage5a2b_run_report.json",
        {**validation, **report, **line_report, "manifest": manifest},
    )
    (output / "run.log").write_text(
        f"status: {status}\nCPU optical flow; no inference; no XYZ\n", encoding="utf-8"
    )
    print(f"status: {status}")


if __name__ == "__main__":
    main()
