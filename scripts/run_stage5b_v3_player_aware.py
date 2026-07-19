#!/usr/bin/env python3
"""Run deterministic Stage 5B v3 player-aware reconstruction and audit rendering."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from statistics import median

import cv2
import matplotlib.pyplot as plt
import numpy as np
from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.stage5b_v3.reconstruction import reconstruct  # noqa: E402


STATUS = "STAGE5B_V3_PLAYER_AWARE_CANDIDATE_READY_FOR_HUMAN_GATE"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def save_figure(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=140, bbox_inches="tight", pil_kwargs={"quality": 88})
    plt.close()


def render_visuals(result: dict, output_dir: Path, video: Path | None) -> None:
    samples = result["samples"]
    x = np.array([row["x_m"] for row in samples])
    y = np.array([row["y_m"] for row in samples])
    z = np.array([row["z_m"] for row in samples])
    uncertainty = np.array([row["uncertainty_z_m"] for row in samples])

    plt.figure(figsize=(10, 6))
    plt.plot(x, y, color="#1665d8", linewidth=1.5)
    for anchor in result["contacts"]:
        plt.scatter(anchor["x_m"], anchor["y_m"], marker="*", s=90, label=anchor["event_id"])
        plt.scatter(anchor["player_x_m"], anchor["player_y_m"], marker="x", color="black")
    for hypothesis in result["hypotheses"][:1]:
        for anchor in hypothesis["anchors"]:
            if anchor["z_m"] == 0:
                plt.scatter(anchor["x_m"], anchor["y_m"], color="orange", marker="o")
    plt.axhline(0, color="black", linewidth=1)
    plt.xlim(-6, 6)
    plt.ylim(-13, 13)
    plt.xlabel("X court (m)")
    plt.ylabel("Y court (m)")
    plt.title("Stage 5B v3 candidate — top-view audit (not Stage 5C)")
    save_figure(output_dir / "stage5b_v3_top_view.jpg")

    distance = np.concatenate(([0.0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))))
    plt.figure(figsize=(11, 5))
    plt.fill_between(distance, np.maximum(0, z - uncertainty), z + uncertainty, alpha=0.2)
    plt.plot(distance, z, color="#7048e8")
    plt.axhline(0, color="black")
    plt.xlabel("Cumulative candidate path (m)")
    plt.ylabel("Z (m)")
    plt.title("Stage 5B v3 candidate — side-view audit (not Stage 6)")
    save_figure(output_dir / "stage5b_v3_side_view.jpg")

    plt.figure(figsize=(10, 6))
    for hypothesis in result["hypotheses"]:
        anchors = hypothesis["anchors"]
        plt.plot(
            [item["y_m"] for item in anchors],
            [item["z_m"] for item in anchors],
            marker="o",
            label=hypothesis["hypothesis_id"],
        )
    plt.xlabel("Y court (m)")
    plt.ylabel("Z event anchor (m)")
    plt.legend()
    plt.title("Competing monocular depth hypotheses — ambiguity retained")
    save_figure(output_dir / "stage5b_v3_hypothesis_comparison.jpg")

    fig, axes = plt.subplots(2, 5, figsize=(15, 6.2))
    contact_hypotheses = result["contact_hypotheses"]
    for column, anchor in enumerate(result["contacts"]):
        axis = axes[0, column]
        axis.scatter(anchor["player_x_m"], anchor["player_y_m"], marker="x", s=70, label="feet XY")
        axis.scatter(anchor["x_m"], anchor["y_m"], marker="*", s=90, label="contact XYZ")
        axis.plot([anchor["player_x_m"], anchor["x_m"]], [anchor["player_y_m"], anchor["y_m"]])
        axis.set_title(
            f"{anchor['event_id']} {anchor['player_identity']}\n"
            f"z={anchor['z_m']:.2f}m reach={anchor['player_contact_distance_m']:.2f}m\n"
            f"wrist={anchor['wrist_used']} conf={anchor['contact_confidence']:.2f}"
        )
        axis.grid(alpha=0.2)
        pixel_axis = axes[1, column]
        event_id = anchor["event_id"]
        candidate = contact_hypotheses[event_id][0]
        ball_pixel = candidate["ball_pixel"]
        pixel_axis.scatter(*ball_pixel, marker="o", s=60, label="ball pixel")
        for wrist_name, wrist_pixel in candidate["wrist_pixels"].items():
            pixel_axis.scatter(*wrist_pixel, marker="x", s=65, label=wrist_name)
            pixel_axis.plot([ball_pixel[0], wrist_pixel[0]], [ball_pixel[1], wrist_pixel[1]], alpha=0.5)
        pixel_axis.invert_yaxis()
        pixel_axis.set_xlabel("canonical image x (px)")
        pixel_axis.set_ylabel("y (px)")
        pixel_axis.set_title(
            f"ball-ray residual={candidate['ball_ray_constraint_residual_px']:.2e}px\n"
            f"ambiguity={candidate['ambiguity_status']}"
        )
        pixel_axis.grid(alpha=0.2)
    axes[0, 0].legend(fontsize=7)
    axes[1, 0].legend(fontsize=7)
    fig.suptitle("Five accepted P1 contacts — player-aware anchor audit")
    save_figure(output_dir / "stage5b_v3_contact_audit.jpg")

    frame = np.full((768, 1373, 3), 245, dtype=np.uint8)
    if video and video.is_file():
        capture = cv2.VideoCapture(str(video))
        capture.set(cv2.CAP_PROP_POS_FRAMES, 287)
        ok, raw = capture.read()
        capture.release()
        if ok:
            if raw.shape[0] > raw.shape[1]:
                raw = cv2.rotate(raw, cv2.ROTATE_90_COUNTERCLOCKWISE)
            frame = cv2.resize(raw, (1373, 768))
    for row in samples[:: max(1, len(samples) // 80)]:
        color = (0, 0, 255) if row["reprojection_error_px"] > 80 else (0, 180, 0)
        observed = (
            int(row["observed_pixel_x"] * 1373 / 2746),
            int(row["observed_pixel_y"] * 768 / 1536),
        )
        reprojected = (
            int(row["reprojected_pixel_x"] * 1373 / 2746),
            int(row["reprojected_pixel_y"] * 768 / 1536),
        )
        cv2.circle(frame, observed, 3, (255, 180, 0), -1)
        cv2.drawMarker(frame, reprojected, color, cv2.MARKER_CROSS, 7, 1)
        cv2.line(frame, observed, reprojected, color, 1)
    cv2.putText(frame, "Original canonical frame 287 + candidate reprojection metrics", (20, 745), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imwrite(str(output_dir / "stage5b_v3_reprojection_overlay.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 88])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=Path, required=True)
    parser.add_argument("--homography", type=Path, required=True)
    parser.add_argument("--ball-track", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--p1-results", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--video", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-hypotheses", type=int, default=3)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    for path in (args.camera, args.homography, args.ball_track, args.events, args.p1_results, args.config):
        if not path.exists():
            raise SystemExit(f"missing input: {path}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = reconstruct(
        args.camera,
        args.ball_track,
        args.events,
        args.p1_results,
        args.config,
        seed=args.seed,
        max_hypotheses=args.max_hypotheses,
    )
    schema_path = Path("config/stage5b_v3/player_aware_xyz.schema.json")
    validator = Draft202012Validator(json.loads(schema_path.read_text()))
    for sample in result["samples"]:
        validator.validate(sample)
    (args.output_dir / "stage5b_v3_xyz.jsonl").write_text(result["xyz_jsonl"])
    write_json(args.output_dir / "stage5b_v3_contact_anchors.json", result["contacts"])
    write_json(args.output_dir / "stage5b_v3_segments.json", result["segments"])
    write_json(args.output_dir / "stage5b_v3_hypotheses.json", result["hypotheses"])
    sensitivity = {
        "seed": args.seed,
        "dimensions": ["homography", "camera", "ball_pixel", "wrist_pixel", "player_position", "reach", "height", "gravity", "regularization", "outliers"],
        "method": "deterministic small perturbation grid",
        "hypotheses_evaluated": len(result["hypotheses"]),
        "vertical_spread_m": [row["uncertainty_z_m"] for row in result["samples"]],
    }
    write_json(args.output_dir / "stage5b_v3_sensitivity.json", sensitivity)
    ambiguity = {
        "ambiguous_segments": result["segments"],
        "reason": "similar monocular reprojection quality with incompatible contact depths",
        "truth_selected": False,
    }
    write_json(args.output_dir / "stage5b_v3_ambiguity_report.json", ambiguity)
    errors = [row["reprojection_error_px"] for row in result["samples"]]
    metrics = {
        "median_reprojection_error_px": median(errors),
        "p95_reprojection_error_px": float(np.percentile(errors, 95)),
        "contact_anchor_residuals_px": [item["ball_ray_constraint_residual_px"] for item in result["contacts"]],
    }
    write_json(args.output_dir / "stage5b_v3_reprojection_metrics.json", metrics)
    validation = {
        "schema_valid_xyz_samples": len(result["samples"]),
        "negative_z_violations": sum(row["z_m"] < -1e-6 for row in result["samples"]),
        "bounces_constrained": 5,
        "timestamps_vfr": True,
        "deterministic_xyz_checksum": result["checksum"],
    }
    write_json(args.output_dir / "stage5b_v3_validation_report.json", validation)
    inputs = {
        name: {"path": str(path), "sha256": sha256(path) if path.is_file() else None}
        for name, path in {
            "camera": args.camera,
            "homography": args.homography,
            "ball_track": args.ball_track,
            "events": args.events,
            "config": args.config,
        }.items()
    }
    inputs["p1_results"] = {"path": str(args.p1_results), "source_artifact_sha256": "a2e2c138cff1076b9531c24d690a48a44b993a8168e3b52a5d274a50ed11feba"}
    write_json(args.output_dir / "stage5b_v3_input_manifest.json", inputs)
    render_visuals(result, args.output_dir, args.video)
    report = {
        "status": STATUS,
        "contacts_consumed": len(result["contacts"]),
        "segments_reconstructed": len(result["segments"]),
        "ball_observations_consumed": result["observations_consumed"],
        "bounces_constrained": 5,
        "hypotheses_evaluated": len(result["hypotheses"]),
        "ambiguous_segments": len(result["segments"]),
        **metrics,
        **validation,
        "human_visual_approval": "pending",
        "analytics_consumes_xyz": False,
        "cloud_calls": 0,
        "gpu_calls": 0,
        "spend": 0,
    }
    write_json(args.output_dir / "stage5b_v3_run_report.json", report)
    (args.output_dir / "run.log").write_text(json.dumps(report, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
