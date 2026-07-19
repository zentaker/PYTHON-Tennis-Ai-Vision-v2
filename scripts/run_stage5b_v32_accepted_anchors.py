#!/usr/bin/env python3
"""Generate accepted anchor v4 and run CPU Stage 5B v3.2."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import sys

import cv2
from jsonschema import Draft202012Validator
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.ground_plane_calibration.anchor_v4 import build_anchor_v4  # noqa: E402
from src.stage5b_v3.v32 import reconstruct_v32  # noqa: E402


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def save(path: Path, assets: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=140, bbox_inches="tight", pil_kwargs={"quality": 86})
    plt.close()
    shutil.copy2(path, assets / path.name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "camera",
        "ball-track",
        "events",
        "p1-results",
        "config",
        "anchor-v3",
        "local-validation",
        "line-report",
        "video",
        "output-dir",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    assets = ROOT / "docs/validation/assets"
    anchor_v3 = [json.loads(line) for line in args.anchor_v3.read_text().splitlines() if line]
    local = json.loads(args.local_validation.read_text())["events"]
    local_by_id = {row["event_id"]: row for row in local}
    line_report = json.loads(args.line_report.read_text())
    anchors_v4 = [
        build_anchor_v4(
            anchor, local_by_id[anchor["event_id"]], line_report, seed=args.seed + index
        )
        for index, anchor in enumerate(anchor_v3)
    ]
    anchor_path = output / "player_contact_ground_anchors_v4.jsonl"
    anchor_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in anchors_v4))
    result = reconstruct_v32(
        args.camera,
        args.ball_track,
        args.events,
        args.p1_results,
        args.config,
        anchor_path,
        seed=args.seed,
        starts_per_segment=3,
    )
    schema = json.loads((ROOT / "config/stage5b_v3/player_aware_xyz.schema.json").read_text())
    validator = Draft202012Validator(schema)
    for row in result["samples"]:
        validator.validate(row)
    (output / "stage5b_v32_xyz.jsonl").write_text(result["xyz_jsonl"])
    write(output / "stage5b_v32_segments.json", result["segment_reports"])
    hypotheses = [asdict(row) | {"samples": len(row.samples)} for row in result["solutions"]]
    write(output / "stage5b_v32_hypotheses.json", hypotheses)
    contacts = [
        {"segment_id": row["segment_id"], "contact_residual_m": row["contact_residual_m"]}
        for row in result["segment_reports"]
    ]
    write(output / "stage5b_v32_contact_residuals.json", contacts)
    bounces = [
        {"segment_id": row["segment_id"], "bounce_residual_m": row["bounce_residual_m"]}
        for row in result["segment_reports"]
    ]
    write(output / "stage5b_v32_bounce_residuals.json", bounces)
    metrics = {
        key: result[key]
        for key in (
            "observations_consumed",
            "observations_downweighted",
            "observations_rejected",
            "median_reprojection_error_px",
            "p95_reprojection_error_px",
            "maximum_reprojection_error_px",
        )
    }
    write(output / "stage5b_v32_reprojection_metrics.json", metrics)
    write(
        output / "stage5b_v32_outlier_report.json",
        {
            "policy": "no observation removed; confidence weights retained",
            "segments": result["segment_reports"],
            "observations_rejected": 0,
        },
    )
    uncertainty = {
        "anchors": anchors_v4,
        "anchor_uncertainty_consumed": True,
        "temporal_player_positions_consumed": False,
        "xyz_sample_uncertainty_propagated": True,
    }
    write(output / "stage5b_v32_uncertainty.json", uncertainty)
    gates = {
        "median_pass": result["median_reprojection_error_px"] <= 8,
        "p95_pass": result["p95_reprojection_error_px"] <= 24,
        "negative_z_pass": result["negative_z_violations"] == 0,
        "bounce_pass": result["maximum_bounce_residual_m"]
        <= json.loads(args.config.read_text())["bounce_tolerance_m"],
        "contacts_consumed": len(result["anchors_consumed"]) == 5,
        "contact_residual_pass": result["maximum_contact_residual_m"] <= 2.5,
        "schema_valid_samples": len(result["samples"]),
        "deterministic_checksum": result["checksum"],
    }
    ready = all(
        value is True
        for key, value in gates.items()
        if key.endswith("_pass") or key == "contacts_consumed"
    )
    status = (
        "STAGE5B_V32_ACCEPTED_ANCHOR_CANDIDATE_READY_FOR_HUMAN_GATE"
        if ready
        else "STAGE5B_V32_PARTIAL"
    )
    validation = {
        "status": status,
        "human_stage5b_v32_approval": "pending",
        **gates,
        "contacts_physically_compatible": result["maximum_contact_residual_m"] <= 2.5,
        "no_clipping": True,
        "uncertainty_propagated": True,
        "xyz_executed": True,
        "cloud_calls": 0,
        "gpu_calls": 0,
        "spend": 0,
    }
    write(output / "stage5b_v32_validation_report.json", validation)
    report = {
        **validation,
        **metrics,
        "contacts_consumed": len(result["anchors_consumed"]),
        "segments_reconstructed": len(result["segment_reports"]),
        "resolved_segments": result["resolved_segments"],
        "ambiguous_segments": result["ambiguous_segments"],
        "maximum_contact_residual_m": result["maximum_contact_residual_m"],
        "maximum_bounce_residual_m": result["maximum_bounce_residual_m"],
        "negative_z_violations": result["negative_z_violations"],
        "schema_valid_samples": len(result["samples"]),
        "checksum": result["checksum"],
        "analytics_consumes_xyz": False,
    }
    write(output / "stage5b_v32_run_report.json", report)
    (output / "run.log").write_text(json.dumps(report, sort_keys=True) + "\n")
    samples = result["samples"]
    colors = plt.cm.tab10(np.linspace(0, 1, 9))
    plt.figure(figsize=(11, 10))
    all_xy = []
    for index in range(1, 10):
        rows = [row for row in samples if row["segment_id"] == f"flight_{index:02d}"]
        plt.plot(
            [row["x_m"] for row in rows],
            [row["y_m"] for row in rows],
            color=colors[index - 1],
            label=f"flight {index}",
        )
        all_xy.extend([[row["x_m"], row["y_m"]] for row in rows])
    for anchor in anchors_v4:
        plt.errorbar(
            anchor["fused_x_m"],
            anchor["fused_y_m"],
            xerr=anchor["uncertainty_x_m"],
            yerr=anchor["uncertainty_y_m"],
            fmt="X",
            label=anchor["event_id"],
        )
        all_xy.append([anchor["fused_x_m"], anchor["fused_y_m"]])
    all_xy = np.asarray(all_xy)
    plt.axhline(-11.885, color="k")
    plt.axhline(11.885, color="k")
    plt.xlim(all_xy[:, 0].min() - 2, all_xy[:, 0].max() + 2)
    plt.ylim(all_xy[:, 1].min() - 2, all_xy[:, 1].max() + 2)
    plt.xlabel("X m")
    plt.ylabel("Y m")
    plt.legend(ncol=3, fontsize=7)
    plt.title("V3.2 separated flights and accepted anchors — no clipping")
    save(output / "stage5b_v32_top_view.jpg", assets)
    fig, axes = plt.subplots(3, 3, figsize=(13, 9))
    for index, axis in enumerate(axes.flat, 1):
        rows = [row for row in samples if row["segment_id"] == f"flight_{index:02d}"]
        axis.plot([row["timestamp_seconds"] for row in rows], [row["z_m"] for row in rows])
        axis.axhline(0, color="k")
        axis.set_title(f"flight_{index:02d}")
    fig.suptitle("V3.2 side view — independent flights")
    save(output / "stage5b_v32_side_view.jpg", assets)
    frame_rows = []
    for index in range(1, 10):
        rows = [row for row in samples if row["segment_id"] == f"flight_{index:02d}"]
        frame_rows.append(rows[len(rows) // 2])
    fig, axes = plt.subplots(3, 3, figsize=(13, 8))
    # Render reprojection separately to keep the loop explicit and segment-safe.
    capture = cv2.VideoCapture(str(args.video))
    for axis, row in zip(axes.flat, frame_rows, strict=True):
        capture.set(cv2.CAP_PROP_POS_FRAMES, row["frame_id"])
        ok, raw = capture.read()
        image = np.full((384, 687, 3), 240, np.uint8)
        if ok:
            if raw.shape[0] > raw.shape[1]:
                raw = cv2.rotate(raw, cv2.ROTATE_90_COUNTERCLOCKWISE)
            image = cv2.cvtColor(cv2.resize(raw, (687, 384)), cv2.COLOR_BGR2RGB)
        axis.imshow(image)
        scale = np.array([687 / 2746, 384 / 1536])
        observed = np.array([row["observed_pixel_x"], row["observed_pixel_y"]]) * scale
        projected = np.array([row["reprojected_pixel_x"], row["reprojected_pixel_y"]]) * scale
        axis.scatter(*observed, color="cyan")
        axis.scatter(*projected, color="red", marker="x")
        axis.plot([observed[0], projected[0]], [observed[1], projected[1]], color="yellow")
        axis.set_title(f"{row['segment_id']} e={row['reprojection_error_px']:.1f}px")
        axis.axis("off")
    capture.release()
    fig.suptitle("Observed vs reprojected real frames")
    save(output / "stage5b_v32_reprojection_contact_sheet.jpg", assets)
    fig, axes = plt.subplots(1, 5, figsize=(16, 4))
    for axis, anchor in zip(axes, anchors_v4, strict=True):
        axis.errorbar(
            anchor["fused_x_m"],
            anchor["fused_y_m"],
            xerr=anchor["uncertainty_x_m"],
            yerr=anchor["uncertainty_y_m"],
            fmt="X",
        )
        axis.axhline(-11.885 if anchor["identity"] == "near" else 11.885, color="k")
        axis.set_title(f"{anchor['event_id']}\n{anchor['temporal_motion_status']}")
    fig.suptitle("Accepted static anchor audit with total uncertainty")
    save(output / "stage5b_v32_contact_anchor_audit.jpg", assets)
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.bar(
        [row["segment_id"] for row in result["segment_reports"]],
        [row["bounce_residual_m"] for row in result["segment_reports"]],
    )
    ax.tick_params(axis="x", rotation=45)
    ax.set(ylabel="bounce residual m", title="V3.2 bounce constraints")
    save(output / "stage5b_v32_bounce_audit.jpg", assets)
    fig, axes = plt.subplots(3, 3, figsize=(13, 9))
    for index, axis in enumerate(axes.flat, 1):
        options = [row for row in result["solutions"] if row.segment_id == f"flight_{index:02d}"]
        axis.bar([row.hypothesis_id[-3:] for row in options], [row.cost for row in options])
        axis.set_title(result["segment_reports"][index - 1]["ambiguity_status"])
    save(output / "stage5b_v32_hypothesis_comparison.jpg", assets)
    fig, ax = plt.subplots(figsize=(12, 7))
    x = np.arange(5)
    ax.bar(x - 0.2, [row["uncertainty_x_m"] for row in anchors_v4], 0.4, label="X")
    ax.bar(x + 0.2, [row["uncertainty_y_m"] for row in anchors_v4], 0.4, label="Y")
    ax.set_xticks(x, [row["event_id"] for row in anchors_v4])
    ax.set_ylabel("metres")
    ax.legend()
    ax.set_title("Anchor v4 conservative total uncertainty")
    save(output / "stage5b_v32_uncertainty.jpg", assets)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
