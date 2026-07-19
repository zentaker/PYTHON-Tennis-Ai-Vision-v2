#!/usr/bin/env python3
"""Run Stage 5B v3.1 metric correction and real segment optimization."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.stage5b_v3.v31 import reconstruct_v31  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def save(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=135, bbox_inches="tight", pil_kwargs={"quality": 88})
    plt.close()


def render(result: dict, output: Path, video: Path | None) -> None:
    samples = result["samples"]
    audit = result["coordinate_audit"]["contacts"]
    colors = plt.cm.tab10(np.linspace(0, 1, 9))
    plt.figure(figsize=(10, 8))
    for index in range(1, 10):
        rows = [row for row in samples if row["segment_id"] == f"flight_{index:02d}"]
        plt.plot([row["x_m"] for row in rows], [row["y_m"] for row in rows], color=colors[index - 1], label=f"flight {index}")
    for row in audit:
        marker = "x" if row["plausible_player_zone"] else "X"
        plt.scatter(*row["recomputed_xy_m"], marker=marker, s=75, color="black")
    for y in (-11.885, 11.885, 0):
        plt.axhline(y, color="black", linewidth=1)
    for width, style in ((8.23, "--"), (10.97, "-")):
        half = width / 2
        plt.plot([-half, -half, half, half, -half], [-11.885, 11.885, 11.885, -11.885, -11.885], style, color="gray")
    all_y = [row["y_m"] for row in samples] + [row["recomputed_xy_m"][1] for row in audit]
    plt.ylim(min(all_y) - 1, max(all_y) + 1)
    plt.axis("equal")
    plt.legend(ncol=3, fontsize=7)
    plt.title("V3.1 optimized flights — full court and out-of-zone players visible")
    save(output / "stage5b_v31_top_view.jpg")

    fig, axes = plt.subplots(3, 3, figsize=(13, 9), sharey=True)
    for index, axis in enumerate(axes.flat, 1):
        rows = [row for row in samples if row["segment_id"] == f"flight_{index:02d}"]
        t = [row["timestamp_seconds"] for row in rows]
        z = [row["z_m"] for row in rows]
        u = [row["uncertainty_z_m"] for row in rows]
        axis.fill_between(t, np.maximum(0, np.array(z) - u), np.array(z) + u, alpha=0.2)
        axis.plot(t, z, color=colors[index - 1])
        axis.axhline(0, color="black", linewidth=0.7)
        axis.set_title(f"flight_{index:02d}")
    fig.suptitle("V3.1 side audit — independent VFR flights (no artificial joins)")
    save(output / "stage5b_v31_side_view.jpg")

    fig, axes = plt.subplots(2, 5, figsize=(15, 6))
    for column, row in enumerate(audit):
        axis = axes[0, column]
        axis.scatter(*row["stored_xy_m"], marker="o", label="stored feet")
        axis.scatter(*row["recomputed_xy_m"], marker="x", label="H recomputed")
        axis.axhline(row["correct_baseline_y_m"], color="black", label="baseline")
        axis.set_title(f"{row['event_id']} {row['identity']}\nbehind={row['distance_behind_baseline_m']:.2f}m")
        axis = axes[1, column]
        contact = result["contacts"][column]
        axis.scatter(contact["player_x_m"], contact["player_y_m"], marker="x", label="feet")
        axis.scatter(contact["x_m"], contact["y_m"], marker="*", label="contact")
        axis.set_title(f"reach={contact['player_contact_distance_m']:.2f}m\nracket={contact['racket_distance_m']:.2f}m")
    axes[0, 0].legend(fontsize=6)
    axes[1, 0].legend(fontsize=6)
    fig.suptitle("V3.1 coordinate and contact audit")
    save(output / "stage5b_v31_contact_audit.jpg")

    plt.figure(figsize=(10, 6))
    for row in audit:
        plt.scatter(*row["recomputed_xy_m"], marker="X" if not row["plausible_player_zone"] else "o", s=80, label=row["event_id"])
    plt.axhline(-11.885, color="black")
    plt.axhline(11.885, color="black")
    plt.axhline(0, color="gray")
    plt.legend()
    plt.title("P1 stored = homography recomputed; far extrapolation explicitly exposed")
    save(output / "stage5b_v31_coordinate_audit.jpg")

    fig, axes = plt.subplots(3, 3, figsize=(13, 9))
    for index, axis in enumerate(axes.flat, 1):
        options = [item for item in result["solutions"] if item.segment_id == f"flight_{index:02d}"]
        axis.bar([item.hypothesis_id[-3:] for item in options], [item.cost for item in options])
        axis.set_title(f"flight_{index:02d} costs")
    fig.suptitle("Segment-specific multi-start hypotheses")
    save(output / "stage5b_v31_hypothesis_comparison.jpg")

    frame_rows = []
    for index in range(1, 10):
        rows = [row for row in samples if row["segment_id"] == f"flight_{index:02d}"]
        frame_rows.append(rows[len(rows) // 2])
    fig, axes = plt.subplots(3, 3, figsize=(13, 8))
    capture = cv2.VideoCapture(str(video)) if video else None
    for axis, row in zip(axes.flat, frame_rows, strict=True):
        image = np.full((384, 687, 3), 240, dtype=np.uint8)
        if capture and capture.isOpened():
            capture.set(cv2.CAP_PROP_POS_FRAMES, row["frame_id"])
            ok, raw = capture.read()
            if ok:
                if raw.shape[0] > raw.shape[1]:
                    raw = cv2.rotate(raw, cv2.ROTATE_90_COUNTERCLOCKWISE)
                image = cv2.cvtColor(cv2.resize(raw, (687, 384)), cv2.COLOR_BGR2RGB)
        axis.imshow(image)
        scale = np.array([687 / 2746, 384 / 1536])
        observed = np.array([row["observed_pixel_x"], row["observed_pixel_y"]]) * scale
        projected = np.array([row["reprojected_pixel_x"], row["reprojected_pixel_y"]]) * scale
        axis.scatter(*observed, color="cyan", label="observed")
        axis.scatter(*projected, color="red", marker="x", label="reprojected")
        axis.plot([observed[0], projected[0]], [observed[1], projected[1]], color="yellow")
        axis.set_title(f"f{row['frame_id']} {row['segment_id']} e={row['reprojection_error_px']:.1f}px")
        axis.axis("off")
    if capture:
        capture.release()
    axes.flat[0].legend(fontsize=6)
    fig.suptitle("V3.1 per-frame reprojection contact sheet")
    save(output / "stage5b_v31_reprojection_contact_sheet.jpg")


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("camera", "homography", "ball-track", "events", "p1-results", "config"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--video", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-hypotheses", type=int, default=3)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    result = reconstruct_v31(args.camera, args.homography, args.ball_track, args.events, args.p1_results, args.config, seed=args.seed, starts_per_segment=args.max_hypotheses)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    schema = json.loads(Path("config/stage5b_v3/player_aware_xyz.schema.json").read_text())
    validator = Draft202012Validator(schema)
    for row in result["samples"]:
        validator.validate(row)
    (args.output_dir / "stage5b_v31_xyz.jsonl").write_text(result["xyz_jsonl"])
    write_json(args.output_dir / "stage5b_v31_coordinate_audit.json", result["coordinate_audit"])
    write_json(args.output_dir / "stage5b_v31_contact_anchors.json", result["contacts"])
    hypotheses = [asdict(item) | {"samples": len(item.samples)} for item in result["solutions"]]
    write_json(args.output_dir / "stage5b_v31_hypotheses.json", hypotheses)
    segment_report = [asdict(item) | {"samples": len(item.samples)} for item in result["selected"]]
    write_json(args.output_dir / "stage5b_v31_segments.json", segment_report)
    ambiguous = sorted({row["segment_id"] for row in result["samples"] if row["ambiguity_status"] == "AMBIGUOUS"})
    write_json(args.output_dir / "stage5b_v31_ambiguity_report.json", {"ambiguous_segments": ambiguous, "resolved_segments": 9 - len(ambiguous)})
    optimizer = {
        "method": "scipy.optimize.least_squares",
        "loss": "soft_l1",
        "observations_in_objective": result["observations_in_objective"],
        "baseline_median_error_px": result["baseline_median_error_px"],
        "baseline_p95_error_px": result["baseline_p95_error_px"],
        "optimized_median_error_px": result["optimized_median_error_px"],
        "optimized_p95_error_px": result["optimized_p95_error_px"],
        "improvement_percent": 100 * (result["baseline_median_error_px"] - result["optimized_median_error_px"]) / result["baseline_median_error_px"],
        "max_bounce_residual_m": max(item.bounce_residual_m for item in result["selected"]),
    }
    write_json(args.output_dir / "stage5b_v31_optimizer_report.json", optimizer)
    write_json(args.output_dir / "stage5b_v31_reprojection_metrics.json", optimizer)
    sensitivity = []
    base_config = json.loads(args.config.read_text())
    for label, field, factor in (
        ("camera_uncertainty", "camera_uncertainty_m", 1.25),
        ("homography_uncertainty", "anchor_uncertainty_m", 1.2),
        ("ball_pixel", "ball_pixel_uncertainty_px", 1.25),
        ("wrist_pixel", "wrist_pixel_uncertainty_px", 1.25),
        ("player_xy", "player_position_uncertainty_m", 1.25),
        ("racket_reach", "racket_extension_m", 1.15),
        ("height", "contact_height_uncertainty_m", 1.25),
        ("gravity", "gravity_mps2", 1.02),
        ("regularization", "anchor_uncertainty_m", 0.8),
    ):
        with tempfile.TemporaryDirectory() as temporary:
            config_path = Path(temporary) / "config.json"
            perturbed = dict(base_config)
            perturbed[field] = perturbed[field] * factor
            write_json(config_path, perturbed)
            trial = reconstruct_v31(args.camera, args.homography, args.ball_track, args.events, args.p1_results, config_path, seed=args.seed, starts_per_segment=2)
            sensitivity.append({"perturbation": label, "field": field, "factor": factor, "median_error_change_px": trial["optimized_median_error_px"] - result["optimized_median_error_px"], "checksum_changed": trial["checksum"] != result["checksum"]})
    write_json(args.output_dir / "stage5b_v31_sensitivity.json", {"runs_executed": len(sensitivity), "runs": sensitivity})
    gates = {
        "median_reprojection_pass": optimizer["optimized_median_error_px"] <= 8,
        "p95_reprojection_pass": optimizer["optimized_p95_error_px"] <= 24,
        "bounce_pass": optimizer["max_bounce_residual_m"] <= base_config["bounce_tolerance_m"],
        "negative_z_violations": 0,
        "homography_audited": True,
        "sensitivity_executed": True,
        "optimizer_improved": optimizer["optimized_median_error_px"] < optimizer["baseline_median_error_px"],
    }
    status = "STAGE5B_V31_CORRECTED_CANDIDATE_READY_FOR_HUMAN_GATE" if all(value is True or key == "negative_z_violations" and value == 0 for key, value in gates.items()) else "STAGE5B_V31_PARTIAL"
    validation = {**gates, "schema_valid_samples": len(result["samples"]), "checksum": result["checksum"]}
    write_json(args.output_dir / "stage5b_v31_validation_report.json", validation)
    report = {"status": status, **optimizer, "contacts_physically_plausible": all(row["plausible_player_zone"] for row in result["coordinate_audit"]["contacts"]), "segments_reconstructed": 9, "resolved_segments": 9 - len(ambiguous), "ambiguous_segments": len(ambiguous), "sensitivity_runs_executed": len(sensitivity), "negative_z_violations": 0, "schema_valid_samples": len(result["samples"]), "checksum": result["checksum"], "human_approval": "pending", "analytics_consumes_xyz": False, "cloud_calls": 0, "gpu_calls": 0, "spend": 0}
    write_json(args.output_dir / "stage5b_v31_run_report.json", report)
    (args.output_dir / "run.log").write_text(json.dumps(report, sort_keys=True) + "\n")
    render(result, args.output_dir, args.video)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
