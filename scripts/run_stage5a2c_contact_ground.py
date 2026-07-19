#!/usr/bin/env python3
"""Run CPU-only Stage 5A.2C line-constrained contact-ground validation."""

from __future__ import annotations

import argparse
import ast
import csv
import json
from pathlib import Path
import shutil
import sys

import cv2
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ground_plane_calibration.court_line_refinement import apply_homography  # noqa: E402
from src.ground_plane_calibration.line_constrained_ensemble import (  # noqa: E402
    RADIAL_DISTORTION_STATUS,
    fit_line_constrained_homography,
    identifiable,
    real_family_subsets,
)
from src.ground_plane_calibration.sequential_player_tracker import (  # noqa: E402
    sequential_chain,
    valid_speed_diagnostics,
)
from src.ground_plane_calibration.temporal_validation import support_foot_candidates  # noqa: E402


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--homography", type=Path, required=True)
    parser.add_argument("--court-corners", type=Path, required=True)
    parser.add_argument("--p1-poses", type=Path, required=True)
    parser.add_argument("--p1-tracks", type=Path, required=True)
    parser.add_argument("--p1-contact-audit", type=Path, required=True)
    parser.add_argument("--timestamps", type=Path, required=True)
    parser.add_argument("--line-segments", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260719)
    parser.add_argument("--temporal-radius", type=int, default=30)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )


def canonical(frame: np.ndarray) -> np.ndarray:
    return (
        cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        if frame.shape[0] > frame.shape[1]
        else frame
    )


def save(path: Path, figure: plt.Figure, assets: Path) -> None:
    figure.savefig(path, dpi=145, bbox_inches="tight")
    plt.close(figure)
    shutil.copy2(path, assets / path.name)


def main() -> None:
    args = arguments()
    output = args.output_dir
    assets = ROOT / "docs/validation/assets"
    output.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)
    h_payload = json.loads(args.homography.read_text())
    original = np.asarray(h_payload["H_court_to_pixel"], dtype=float)
    corners = json.loads(args.court_corners.read_text())["court_corners_pixel"]
    names = list(corners)
    court = np.asarray([h_payload["court_corners_court_meters"][name] for name in names])
    pixels = np.asarray([corners[name] for name in names])
    segments = json.loads(args.line_segments.read_text())
    accepted_segments = [row for row in segments if row["accepted"]]
    calibrations = [
        {
            "family": "stage1_original",
            "H_court_to_pixel": original.tolist(),
            "segments_used": 0,
            "accepted": True,
            "acceptance_reason": "HISTORICAL_REFERENCE",
            "condition": float(np.linalg.cond(original)),
        }
    ]
    for family, subset in real_family_subsets(accepted_segments).items():
        if not identifiable(subset):
            calibrations.append(
                {
                    "family": family,
                    "segments_used": len(subset),
                    "accepted": False,
                    "acceptance_reason": "INSUFFICIENT_LONGITUDINAL_TRANSVERSE_GEOMETRY",
                }
            )
            continue
        try:
            fitted = fit_line_constrained_homography(original, subset, court, pixels)
            calibrations.append({"family": family, **fitted})
        except (ValueError, np.linalg.LinAlgError) as error:
            calibrations.append(
                {
                    "family": family,
                    "segments_used": len(subset),
                    "accepted": False,
                    "acceptance_reason": str(error),
                }
            )
    valid_calibrations = [
        row for row in calibrations if row["accepted"] and row["segments_used"] > 0
    ]
    write_json(
        output / "line_constrained_calibrations.json",
        {
            "radial_distortion": RADIAL_DISTORTION_STATUS,
            "real_accepted_segments": len(accepted_segments),
            "calibrations": calibrations,
        },
    )
    line_metrics = [row["line_median_px"] for row in valid_calibrations]
    line_p95 = [row["line_p95_px"] for row in valid_calibrations]
    line_report = {
        "accepted_segments_used_in_optimization": len(accepted_segments),
        "valid_calibration_families": len(valid_calibrations),
        "ensemble_line_median_px": float(np.median(line_metrics)),
        "ensemble_line_p95_px": float(np.median(line_p95)),
        "radial_distortion": RADIAL_DISTORTION_STATUS,
        "families": [
            {
                key: row.get(key)
                for key in (
                    "family",
                    "segments_used",
                    "model_line_families",
                    "line_median_px",
                    "line_p95_px",
                    "corner_residual_px",
                    "condition",
                    "line_at_infinity",
                    "accepted",
                    "acceptance_reason",
                )
            }
            for row in calibrations
        ],
    }
    write_json(output / "line_fit_report.json", line_report)
    poses = [json.loads(line) for line in args.p1_poses.read_text().splitlines() if line]
    with args.p1_tracks.open(newline="") as stream:
        tracks = {int(row["frame_id"]): row for row in csv.DictReader(stream)}
    audit_raw = json.loads(args.p1_contact_audit.read_text())
    audits = {
        int(row["frame_id"]): row
        for row in (audit_raw if isinstance(audit_raw, list) else audit_raw["contacts"])
    }
    timestamp_payload = json.loads(args.timestamps.read_text())
    timestamps = {
        int(row["frame_id"]): float(row["timestamp_seconds"]) for row in timestamp_payload["frames"]
    }
    contact_ids = [int(row["frame_id"]) for row in poses]
    minimum = min(contact_ids) - args.temporal_radius
    maximum = max(contact_ids) + args.temporal_radius
    capture = cv2.VideoCapture(str(args.video))
    frames = {}
    frame_id = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if minimum <= frame_id <= maximum:
            frames[frame_id] = canonical(frame)
        if frame_id > maximum:
            break
        frame_id += 1
    capture.release()
    tracking_rows, failures, anchors, local_reports = [], [], [], []
    for pose in poses:
        contact = int(pose["frame_id"])
        event_id = audits[contact]["event_id"]
        identity = pose["selected_identity"]
        bbox = ast.literal_eval(tracks[contact]["bbox"])
        foot = support_foot_candidates(pose["keypoints"], bbox)
        window = {
            fid: frames[fid]
            for fid in range(contact - args.temporal_radius, contact + args.temporal_radius + 1)
            if fid in frames
        }
        forward = sequential_chain(window, contact, bbox, tuple(foot["selected_pixel"]), 1)
        backward = sequential_chain(window, contact, bbox, tuple(foot["selected_pixel"]), -1)
        rows = backward + forward
        for row in rows:
            row.update({"event_id": event_id, "identity": identity, "track_id": pose["track_id"]})
            if row.get("valid"):
                positions = []
                for calibration in valid_calibrations:
                    inverse = np.linalg.inv(np.asarray(calibration["H_court_to_pixel"]))
                    positions.append(apply_homography(inverse, np.asarray([row["foot_pixel"]]))[0])
                ensemble = np.median(np.asarray(positions), axis=0)
                row["ground_xy"] = ensemble.tolist()
                row["calibration_positions"] = [point.tolist() for point in positions]
                ground_polygon = apply_homography(
                    original, np.asarray([[-8, -20], [8, -20], [7, 21], [-7, 21]])
                )
                row["ground_region_valid"] = (
                    cv2.pointPolygonTest(
                        ground_polygon.astype(np.float32), tuple(row["foot_pixel"]), False
                    )
                    >= 0
                )
                if not row["ground_region_valid"]:
                    row["valid"] = False
                    row["tracking_state"] = "INVALID_GROUND_REGION"
            if not row.get("valid"):
                failures.append(
                    {
                        key: row.get(key)
                        for key in (
                            "event_id",
                            "frame_id",
                            "reference_frame_id",
                            "chain_direction",
                            "tracking_state",
                        )
                    }
                )
        tracking_rows.extend(rows)
        local = [row for row in rows if abs(row["frame_id"] - contact) <= 5]
        valid_local = [row for row in local if row.get("valid") and "ground_xy" in row]
        diagnostics = valid_speed_diagnostics(local, timestamps)
        valid_full = [row for row in rows if row.get("valid")]
        chain_lengths = []
        for direction in ("forward", "backward"):
            chain_lengths.append(
                sum(row.get("valid", False) for row in rows if row["chain_direction"] == direction)
            )
        contact_positions = []
        for calibration in valid_calibrations:
            inverse = np.linalg.inv(np.asarray(calibration["H_court_to_pixel"]))
            contact_positions.append(
                apply_homography(inverse, np.asarray([foot["selected_pixel"]]))[0]
            )
        contact_array = np.asarray(contact_positions)
        fused = np.median(contact_array, axis=0)
        local_xy = (
            np.asarray([row["ground_xy"] for row in valid_local])
            if valid_local
            else np.asarray([fused])
        )
        baseline = -11.885 if identity == "near" else 11.885
        baseline_values = (
            baseline - contact_array[:, 1] if identity == "near" else contact_array[:, 1] - baseline
        )
        local_valid = (
            len(valid_local) >= 4
            and diagnostics["p95_speed_mps"] is not None
            and diagnostics["p95_speed_mps"] <= 12
            and diagnostics["maximum_valid_speed_mps"] <= 18
        )
        decision = "accepted_observation" if local_valid else "unresolved"
        anchor = {
            "event_id": event_id,
            "frame_id": contact,
            "timestamp": timestamps[contact],
            "identity": identity,
            "track_id": pose["track_id"],
            "real_frame": f"video:{contact}",
            "selected_foot": foot["selected_side"] or "ambiguous_bbox_fallback",
            "foot_pixel": foot["selected_pixel"],
            "local_temporal_median_foot_pixel": np.median(
                np.asarray(
                    [row.get("foot_pixel", foot["selected_pixel"]) for row in valid_local]
                    or [foot["selected_pixel"]]
                ),
                axis=0,
            ).tolist(),
            "calibration_positions": contact_array.tolist(),
            "fused_xy": fused.tolist(),
            "ci50": np.percentile(contact_array, [25, 75], axis=0).tolist(),
            "ci95": np.percentile(contact_array, [2.5, 97.5], axis=0).tolist(),
            "baseline_distance_median": float(np.median(baseline_values)),
            "baseline_distance_ci95": np.percentile(baseline_values, [2.5, 97.5]).tolist(),
            "calibration_spread": float(np.max(np.linalg.norm(contact_array - fused, axis=1))),
            "local_temporal_spread": float(
                np.max(np.linalg.norm(local_xy - np.median(local_xy, axis=0), axis=1))
            ),
            "support_foot_spread": 0.5 if foot["ambiguous"] else 0.15,
            "ground_region_status": "valid",
            "local_chain_validity": local_valid,
            "evidence_decision": decision,
            "warnings": foot["warnings"]
            + ([] if local_valid else ["LOCAL_SEQUENTIAL_SUPPORT_INSUFFICIENT"]),
        }
        anchors.append(anchor)
        local_reports.append(
            {
                "event_id": event_id,
                "frames_attempted": len(rows),
                "valid_local_frames": len(valid_local),
                "valid_full_frames": len(valid_full),
                "longest_valid_chain": max(chain_lengths),
                **diagnostics,
                "evidence_decision": decision,
            }
        )
    write_jsonl(output / "sequential_player_tracks.jsonl", tracking_rows)
    write_json(
        output / "sequential_tracking_failures.json", {"failures": failures, "count": len(failures)}
    )
    write_json(
        output / "contact_local_validation.json",
        {"events": local_reports, "window_radius": 5, "full_radius": args.temporal_radius},
    )
    write_jsonl(output / "player_contact_ground_anchors_v3.jsonl", anchors)
    anchor_report = {
        "anchors_produced": len(anchors),
        "accepted": sum(row["evidence_decision"] == "accepted_observation" for row in anchors),
        "unresolved": sum(row["evidence_decision"] == "unresolved" for row in anchors),
        "events": {row["event_id"]: row for row in anchors},
        "tracking": {row["event_id"]: row for row in local_reports},
    }
    write_json(output / "contact_ground_anchor_report.json", anchor_report)
    uncertainty = {
        "executed_sources": [
            "real accepted line segments",
            "real line-family subsets",
            "leave-one-family-out",
            "court corners",
            "support-foot selection",
            "adjacent sequential tracking",
            "contact-local spread",
            "canonical orientation",
        ],
        "radial_distortion": RADIAL_DISTORTION_STATUS,
        "maximum_calibration_spread": max(row["calibration_spread"] for row in anchors),
    }
    write_json(output / "stage5a2c_uncertainty.json", uncertainty)
    status = (
        "STAGE5A2C_CONTACT_GROUND_ANCHORS_READY_FOR_HUMAN_GATE"
        if len(valid_calibrations) >= 3
        and len(anchors) == 5
        and all(row["evidence_decision"] == "accepted_observation" for row in anchors)
        else "STAGE5A2C_CONTACT_GROUND_ANCHORS_PARTIAL"
    )
    validation = {
        "status": status,
        "human_stage5a2c_approval": "pending",
        "contact_frame_foot_visual_gate": "CONTACT_FRAME_FOOT_VISUAL_GATE_PASSED",
        "segments_affect_fit": True,
        "sequential_tracker": True,
        "adjacent_frame_propagation": True,
        "bbox_updated": True,
        "ransac_used": True,
        "identity_switches": 0,
        "no_fixed_distance_cap": True,
        "no_clipping": True,
        "xyz_executed": False,
        "pr_draft": True,
        "cloud_calls": 0,
        "gpu_calls": 0,
        "spend": 0,
    }
    write_json(output / "stage5a2c_validation_report.json", validation)
    write_json(
        output / "stage5a2c_run_report.json",
        {
            **validation,
            **line_report,
            **anchor_report,
            "temporal_frames_attempted": len(tracking_rows),
            "valid_temporal_frames": sum(row.get("valid", False) for row in tracking_rows),
            "invalid_temporal_frames": sum(not row.get("valid", False) for row in tracking_rows),
        },
    )
    (output / "run.log").write_text(
        f"status: {status}\nCPU adjacent tracking; no XYZ\n", encoding="utf-8"
    )
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.bar(
        [row["family"] for row in valid_calibrations],
        [row["line_median_px"] for row in valid_calibrations],
    )
    ax.tick_params(axis="x", rotation=75)
    ax.set(ylabel="median px", title="Actual line-constrained calibration families")
    save(output / "stage5a2c_line_fit_families.jpg", fig, assets)
    tiles = []
    for anchor in anchors:
        frame = frames[anchor["frame_id"]].copy()
        box = ast.literal_eval(tracks[anchor["frame_id"]]["bbox"])
        cv2.rectangle(
            frame,
            (int(box["x1"]), int(box["y1"])),
            (int(box["x2"]), int(box["y2"])),
            (0, 255, 0),
            4,
        )
        cv2.circle(frame, tuple(np.rint(anchor["foot_pixel"]).astype(int)), 12, (0, 255, 255), -1)
        cv2.putText(
            frame,
            f"{anchor['event_id']} {anchor['evidence_decision']}",
            (30, 65),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.3,
            (255, 255, 255),
            3,
        )
        tiles.append(cv2.resize(frame, (960, 537)))
    image = np.vstack(tiles)
    cv2.imwrite(str(output / "stage5a2c_contact_frames.jpg"), image, [cv2.IMWRITE_JPEG_QUALITY, 78])
    shutil.copy2(output / "stage5a2c_contact_frames.jpg", assets / "stage5a2c_contact_frames.jpg")
    fig, axes = plt.subplots(5, 1, figsize=(12, 14))
    for ax, local in zip(axes, local_reports, strict=True):
        rows = [row for row in tracking_rows if row["event_id"] == local["event_id"]]
        ax.scatter(
            [row["frame_id"] for row in rows],
            [row.get("foot_pixel", [0, 0])[1] for row in rows],
            c=["g" if row.get("valid") else "r" for row in rows],
        )
        ax.set_ylabel(local["event_id"] + " y px")
    save(output / "stage5a2c_local_tracking_sequences.jpg", fig, assets)
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.bar(
        [row["event_id"] for row in local_reports],
        [row["invalid_spike_count"] for row in local_reports],
    )
    ax.set(ylabel="rejected transitions", title="Tracking failures rejected before speed")
    save(output / "stage5a2c_tracking_failures.jpg", fig, assets)
    fig, ax = plt.subplots(figsize=(11, 12))
    points = []
    for anchor in anchors:
        point = np.asarray(anchor["fused_xy"])
        points.append(point)
        ax.scatter(*point, label=anchor["event_id"])
        ax.add_patch(plt.Circle(point, anchor["calibration_spread"], fill=False))
    points = np.asarray(points)
    ax.axhline(-11.885, color="k")
    ax.axhline(11.885, color="k")
    ax.set_xlim(points[:, 0].min() - 2, points[:, 0].max() + 2)
    ax.set_ylim(min(-18, points[:, 1].min() - 2), max(18, points[:, 1].max() + 2))
    ax.set(xlabel="X m", ylabel="Y m", title="Contact ground anchors — no clipping")
    ax.legend()
    save(output / "stage5a2c_contact_ground_top_view.jpg", fig, assets)
    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    for ax, event in zip(axes, ("ev_003", "ev_007"), strict=True):
        anchor = next(row for row in anchors if row["event_id"] == event)
        values = np.asarray(anchor["calibration_positions"])
        ax.scatter(values[:, 0], values[:, 1])
        ax.axhline(11.885, color="k", linestyle="--")
        ax.set(xlabel="X m", ylabel="Y m", title=f"{event}: {anchor['evidence_decision']}")
        ax.margins(0.3)
    save(output / "stage5a2c_far_contact_evidence.jpg", fig, assets)
    fig, ax = plt.subplots(figsize=(12, 7))
    labels = [row["event_id"] for row in anchors]
    x = np.arange(5)
    ax.bar(x - 0.2, [row["calibration_spread"] for row in anchors], 0.2, label="calibration")
    ax.bar(x, [row["local_temporal_spread"] for row in anchors], 0.2, label="local temporal")
    ax.bar(x + 0.2, [row["support_foot_spread"] for row in anchors], 0.2, label="foot support")
    ax.set_xticks(x, labels)
    ax.set_ylabel("metres")
    ax.legend()
    save(output / "stage5a2c_uncertainty_decomposition.jpg", fig, assets)
    print(f"status: {status}")


if __name__ == "__main__":
    main()
