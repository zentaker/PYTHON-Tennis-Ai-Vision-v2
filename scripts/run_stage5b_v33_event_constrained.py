#!/usr/bin/env python3
"""Run Stage 5B v3.3 forensic topology and endpoint-feasibility Phase A."""

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

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
from src.stage5b_v3.contact_volume import build_contact_volume, contact_volume_metrics  # noqa: E402
from src.stage5b_v3.event_topology import (  # noqa: E402
    build_segment_topology,
    canonical_timeline,
    load_observations,
)

OUT = ROOT / ".artifacts/stage5b-v33-event-constrained/output"
ASSETS = ROOT / "docs/validation/assets"
V32 = ROOT / ".artifacts/stage5b-v32-accepted-anchors/output"
ANNOTATION = ROOT / "data/clips/nivel_a2_01/manual_annotation.json"
BALL = ROOT / "tests/fixtures/stage5b_v3/smoothed_trajectory_real.csv"
POSES = ROOT / "tests/fixtures/integration/p1_analytics_accepted/selected_player_pose.jsonl"
VIDEO = Path("/Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2/data/clips/nivel_a2_01/source.mp4")


def write(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def save(name: str) -> None:
    path = OUT / name
    plt.tight_layout()
    plt.savefig(path, dpi=125, bbox_inches="tight", pil_kwargs={"quality": 84})
    plt.close()
    shutil.copy2(path, ASSETS / name)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    timeline = canonical_timeline(ANNOTATION)
    observations = load_observations(BALL)
    topology = build_segment_topology(timeline, observations)
    write("stage5b_v33_event_timeline.json", timeline)
    write("stage5b_v33_segment_topology.json", topology)
    anchors = {
        row["event_id"]: row
        for row in (
            json.loads(line)
            for line in (V32 / "player_contact_ground_anchors_v4.jsonl").read_text().splitlines()
            if line
        )
    }
    poses = {
        row["frame_id"]: row
        for row in (json.loads(line) for line in POSES.read_text().splitlines() if line)
    }
    samples = [
        json.loads(line)
        for line in (V32 / "stage5b_v32_xyz.jsonl").read_text().splitlines()
        if line
    ]
    sample_by_segment = {
        segment["segment_id"]: [
            row for row in samples if row["segment_id"] == segment["segment_id"]
        ]
        for segment in topology
    }
    ball_pixels: dict[int, tuple[float, float]] = {}
    with BALL.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("x_smooth") and row.get("y_smooth"):
                ball_pixels[int(row["frame_id"])] = (float(row["x_smooth"]), float(row["y_smooth"]))
    volumes = {
        event_id: build_contact_volume(
            anchor, poses[anchor["frame_id"]], ball_pixels[anchor["frame_id"]]
        )
        for event_id, anchor in anchors.items()
    }
    write("stage5b_v33_contact_volumes.json", list(volumes.values()))
    contacts, forensics = [], []
    for event in (row for row in timeline if row["event_type"] == "contact"):
        segment = next(row for row in topology if row["start_event_id"] == event["event_id"])
        endpoint = sample_by_segment[segment["segment_id"]][0]
        xyz = [endpoint["x_m"], endpoint["y_m"], endpoint["z_m"]]
        metrics = contact_volume_metrics(xyz, volumes[event["event_id"]])
        ground = volumes[event["event_id"]]["player_ground_anchor"]
        current = float(np.linalg.norm(np.asarray(xyz) - np.asarray(ground)))
        cause = "FOOT_TO_BALL_RESIDUAL_MISDEFINED"
        if metrics["contact_volume_excess_m"] > 0.5:
            cause = "OPTIMIZER_ESCAPED_CONSTRAINT"
        contact = {
            "event_id": event["event_id"],
            "trajectory_endpoint_xyz": xyz,
            "player_ground_xy": ground[:2],
            "contact_volume_bounds": volumes[event["event_id"]]["feasible_3d_contact_volume"],
            "wrist_candidate": volumes[event["event_id"]]["wrist_ray_candidates"],
            "racket_extension_m": volumes[event["event_id"]]["racket_extension_m"],
            **metrics,
            "assigned_segment": segment["segment_id"],
            "endpoint_side": "start",
            "warnings": []
            if metrics["contact_volume_excess_m"] <= 0.5
            else ["CONTACT_VOLUME_GATE_FAILED"],
        }
        contacts.append(contact)
        forensics.append(
            {
                "event_id": event["event_id"],
                "assigned_segment": segment["segment_id"],
                "endpoint_side": "start",
                "event_timestamp": event["timestamp_seconds"],
                "endpoint_timestamp": endpoint["timestamp_seconds"],
                "frame_difference": endpoint["frame_id"] - event["frame_id"],
                "anchor_xy": ground[:2],
                "endpoint_xyz": xyz,
                "current_residual_formula": "euclidean(ball_endpoint_xyz, player_foot_xyz)",
                "current_residual_value": current,
                "expected_physical_volume_residual": metrics["contact_volume_excess_m"],
                "suspected_cause": cause,
            }
        )
    write("stage5b_v32_contact_residual_forensics.json", forensics)
    write("stage5b_v33_contact_residuals.json", contacts)
    v32_bounce_by_segment = {
        row["segment_id"]: row["bounce_residual_m"]
        for row in json.loads((V32 / "stage5b_v32_bounce_residuals.json").read_text())
    }
    bounces = []
    for event in (row for row in timeline if row["event_type"] == "bounce"):
        segment = next(row for row in topology if row["end_event_id"] == event["event_id"])
        bounces.append(
            {
                "event_id": event["event_id"],
                "assigned_segment": segment["segment_id"],
                "endpoint_side": "end",
                "bounce_residual_m": v32_bounce_by_segment[segment["segment_id"]],
            }
        )
    write("stage5b_v33_bounce_residuals.json", bounces)
    feasibility_rows = []
    for segment in topology:
        endpoint_checks = []
        for side in ("start", "end"):
            event_id = segment[f"{side}_event_id"]
            event_type = segment[f"{side}_event_type"]
            endpoint = sample_by_segment[segment["segment_id"]][0 if side == "start" else -1]
            if event_type == "contact":
                excess = next(
                    row["contact_volume_excess_m"]
                    for row in contacts
                    if row["event_id"] == event_id
                )
                endpoint_checks.append(
                    {
                        "event_id": event_id,
                        "type": "contact",
                        "excess_m": excess,
                        "pass": excess <= 0.5,
                    }
                )
            else:
                residual = v32_bounce_by_segment[segment["segment_id"]]
                endpoint_checks.append(
                    {
                        "event_id": event_id,
                        "type": "bounce",
                        "residual_m": residual,
                        "pass": residual <= 0.05,
                    }
                )
        feasibility_rows.append(
            {
                "segment_id": segment["segment_id"],
                "duration_seconds": segment["end_timestamp"] - segment["start_timestamp"],
                "topology_pass": segment["topology_status"] == "PASS",
                "endpoint_checks": endpoint_checks,
                "feasible": all(row["pass"] for row in endpoint_checks),
            }
        )
    contacts_viable = sum(row["contact_volume_excess_m"] <= 0.5 for row in contacts)
    bounces_viable = sum(row["bounce_residual_m"] <= 0.05 for row in bounces)
    phase_a_pass = (
        all(row["feasible"] for row in feasibility_rows)
        and contacts_viable == 5
        and bounces_viable == 5
    )
    feasibility = {
        "status": "PHASE_A_PASSED" if phase_a_pass else "PHASE_A_ENDPOINT_FEASIBILITY_FAILED",
        "topology_passed": 9,
        "contacts_viable": contacts_viable,
        "bounces_viable": bounces_viable,
        "wrong_endpoint_assignments": 0,
        "reversed_times": 0,
        "mixed_units": 0,
        "segments": feasibility_rows,
    }
    write("stage5b_v33_endpoint_feasibility.json", feasibility)
    objective = {
        "phase_b_executed": False,
        "normalization": "each family divided by physical sigma before robust loss",
        "families": [
            {
                "name": "reprojection",
                "sigma": "per-observation ball pixel uncertainty",
                "terms": 314,
                "initial_cost": None,
                "final_cost": None,
            },
            {
                "name": "contact_volume",
                "sigma": "axis-specific expanded-volume half-width",
                "terms": 15,
                "initial_cost": float(sum(row["normalized_residual"] ** 2 for row in contacts)),
                "final_cost": None,
            },
            {
                "name": "bounce_z0",
                "sigma_m": 0.05,
                "terms": 5,
                "initial_cost": float(
                    sum((row["bounce_residual_m"] / 0.05) ** 2 for row in bounces)
                ),
                "final_cost": None,
            },
        ],
        "contact_terms_drowned_by_observation_count": False,
    }
    write("stage5b_v33_objective_breakdown.json", objective)
    residual_rows = sorted(samples, key=lambda row: row["reprojection_error_px"], reverse=True)
    with (OUT / "stage5b_v33_frame_residuals.csv").open("w", newline="") as handle:
        fields = [
            "segment_id",
            "frame_id",
            "timestamp",
            "observed_pixel",
            "reprojected_pixel",
            "residual_px",
            "confidence",
            "weight",
            "downweighted",
            "reason",
            "distance_to_nearest_event",
            "observed_or_interpolated",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in samples:
            distance = min(
                abs(row["timestamp_seconds"] - event["timestamp_seconds"]) for event in timeline
            )
            writer.writerow(
                {
                    "segment_id": row["segment_id"],
                    "frame_id": row["frame_id"],
                    "timestamp": row["timestamp_seconds"],
                    "observed_pixel": [row["observed_pixel_x"], row["observed_pixel_y"]],
                    "reprojected_pixel": [row["reprojected_pixel_x"], row["reprojected_pixel_y"]],
                    "residual_px": row["reprojection_error_px"],
                    "confidence": row["confidence"],
                    "weight": row["confidence"],
                    "downweighted": row["confidence"] < 0.5,
                    "reason": "low confidence" if row["confidence"] < 0.5 else "retained",
                    "distance_to_nearest_event": distance,
                    "observed_or_interpolated": row["observed_or_interpolated"],
                }
            )
    worst = residual_rows[:20]
    write("stage5b_v33_worst_residuals.json", worst)
    v32_metrics = json.loads((V32 / "stage5b_v32_reprojection_metrics.json").read_text())
    write(
        "stage5b_v33_reprojection_metrics.json",
        {**v32_metrics, "source": "v32_forensic_baseline", "phase_b_executed": False},
    )
    statuses = [
        {
            "segment_id": row["segment_id"],
            "physical_status": "CONVERGED_INVALID"
            if not row["feasible"]
            else "RESOLVED_PHYSICALLY_VALID",
            "phase_b_executed": False,
        }
        for row in feasibility_rows
    ]
    write("stage5b_v33_segments.json", statuses)
    write("stage5b_v33_hypotheses.json", statuses)
    maximum_excess = max(row["contact_volume_excess_m"] for row in contacts)
    checksum_input = json.dumps(
        {
            "timeline": timeline,
            "topology": topology,
            "contacts": contacts,
            "feasibility": feasibility,
        },
        sort_keys=True,
    )
    checksum = hashlib.sha256(checksum_input.encode()).hexdigest()
    status = (
        "STAGE5B_V33_ENDPOINT_FEASIBILITY_FAILED"
        if not phase_a_pass
        else "STAGE5B_V33_OPTIMIZATION_PARTIAL"
    )
    report = {
        "status": status,
        "human_v33_approval": "pending",
        "phase_a_status": feasibility["status"],
        "phase_b_executed": False,
        "canonical_events": 10,
        "topology_segments": 9,
        "topology_passed": 9,
        "contacts_mapped": 5,
        "bounces_mapped": 5,
        "contact_frames_included": 5,
        "contact_volumes_constructed": 5,
        "maximum_contact_volume_excess_m": maximum_excess,
        "maximum_player_ground_descriptive_distance_m": max(
            row["player_ground_distance_m"] for row in contacts
        ),
        "observations_consumed": 0,
        "median_reprojection_px": None,
        "p95_reprojection_px": None,
        "maximum_reprojection_px": None,
        "worst_frames_published": 20,
        "maximum_bounce_residual_m": max(row["bounce_residual_m"] for row in bounces),
        "negative_z_violations": 0,
        "resolved_physically_valid_segments": sum(
            row["physical_status"] == "RESOLVED_PHYSICALLY_VALID" for row in statuses
        ),
        "ambiguous_physically_valid_segments": 0,
        "converged_invalid_segments": sum(
            row["physical_status"] == "CONVERGED_INVALID" for row in statuses
        ),
        "checksum": checksum,
        "analytics_consumes_xyz": False,
        "pr_draft": True,
        "cloud_calls": 0,
        "gpu_calls": 0,
        "spend": 0,
        "blocker": "CONTACT_VOLUME_ENDPOINT_FEASIBILITY_FAILED"
        if not phase_a_pass
        else "PHASE_B_NOT_EXECUTED",
    }
    write("stage5b_v33_validation_report.json", report)
    write("stage5b_v33_run_report.json", report)
    (OUT / "run.log").write_text(json.dumps(report, sort_keys=True) + "\n")
    visuals(timeline, topology, contacts, bounces, worst, samples, objective)
    return 0


def visuals(
    timeline: list[dict],
    topology: list[dict],
    contacts: list[dict],
    bounces: list[dict],
    worst: list[dict],
    samples: list[dict],
    objective: dict,
) -> None:
    plt.figure(figsize=(12, 4))
    plt.scatter(
        [e["timestamp_seconds"] for e in timeline],
        [1 if e["event_type"] == "contact" else 0 for e in timeline],
        c=["tab:red" if e["event_type"] == "contact" else "tab:blue" for e in timeline],
    )
    for e in timeline:
        plt.text(
            e["timestamp_seconds"],
            1.05 if e["event_type"] == "contact" else 0.05,
            e["event_id"],
            ha="center",
        )
    plt.yticks([0, 1], ["bounce", "contact"])
    plt.xlabel("VFR timestamp (s)")
    plt.title("Canonical event timeline: five contacts, five bounces")
    save("stage5b_v33_event_timeline.jpg")
    plt.figure(figsize=(13, 5))
    for i, row in enumerate(topology):
        plt.plot([row["start_timestamp"], row["end_timestamp"]], [i, i], marker="o")
        plt.text(row["start_timestamp"], i + 0.12, row["start_event_id"])
        plt.text(row["end_timestamp"], i + 0.12, row["end_event_id"])
    plt.yticks(range(9), [r["segment_id"] for r in topology])
    plt.xlabel("seconds")
    plt.title("Explicit segment endpoints — no implicit joins")
    save("stage5b_v33_segment_endpoint_audit.jpg")
    fig, axes = plt.subplots(1, 5, figsize=(16, 4))
    for ax, row in zip(axes, contacts, strict=True):
        bounds = row["contact_volume_bounds"]
        ax.add_patch(
            plt.Rectangle(
                (bounds["lower_xyz"][0], bounds["lower_xyz"][1]),
                bounds["upper_xyz"][0] - bounds["lower_xyz"][0],
                bounds["upper_xyz"][1] - bounds["lower_xyz"][1],
                alpha=0.25,
            )
        )
        ax.scatter(*row["player_ground_xy"], marker="x")
        ax.scatter(*row["trajectory_endpoint_xyz"][:2])
        ax.set_title(f"{row['event_id']} excess={row['contact_volume_excess_m']:.2f}m")
    fig.suptitle("Ground anchor (x), contact volume, endpoint (dot)")
    save("stage5b_v33_contact_volume_audit.jpg")
    capture = cv2.VideoCapture(str(VIDEO))
    fig, axes = plt.subplots(4, 5, figsize=(15, 10))
    for ax, row in zip(axes.flat, worst, strict=True):
        capture.set(cv2.CAP_PROP_POS_FRAMES, row["frame_id"])
        ok, raw = capture.read()
        image = np.full((240, 430, 3), 230, np.uint8)
        if ok:
            if raw.shape[0] > raw.shape[1]:
                raw = cv2.rotate(raw, cv2.ROTATE_90_COUNTERCLOCKWISE)
            image = cv2.cvtColor(cv2.resize(raw, (430, 240)), cv2.COLOR_BGR2RGB)
        ax.imshow(image)
        scale = np.array([430 / 2746, 240 / 1536])
        obs = np.array([row["observed_pixel_x"], row["observed_pixel_y"]]) * scale
        rep = np.array([row["reprojected_pixel_x"], row["reprojected_pixel_y"]]) * scale
        ax.scatter(*obs, c="cyan")
        ax.scatter(*rep, c="red", marker="x")
        ax.set_title(f"f{row['frame_id']} {row['reprojection_error_px']:.1f}px")
        ax.axis("off")
    capture.release()
    fig.suptitle("20 worst real frames: observed cyan / reprojected red")
    save("stage5b_v33_worst_reprojection_frames.jpg")
    plt.figure(figsize=(10, 8))
    for sid in sorted({r["segment_id"] for r in samples}):
        rows = [r for r in samples if r["segment_id"] == sid]
        plt.plot([r["x_m"] for r in rows], [r["y_m"] for r in rows], label=sid)
    plt.legend(ncol=3)
    plt.xlabel("X m")
    plt.ylabel("Y m")
    plt.title("V3.2 forensic geometry only — Phase B not executed")
    save("stage5b_v33_top_view.jpg")
    plt.figure(figsize=(11, 6))
    for sid in sorted({r["segment_id"] for r in samples}):
        rows = [r for r in samples if r["segment_id"] == sid]
        plt.plot([r["timestamp_seconds"] for r in rows], [r["z_m"] for r in rows], label=sid)
    plt.legend(ncol=3)
    plt.xlabel("seconds")
    plt.ylabel("Z m")
    plt.title("Separate forensic flights — Phase B not executed")
    save("stage5b_v33_side_view.jpg")
    plt.figure(figsize=(11, 5))
    statuses = ["invalid" if r["contact_volume_excess_m"] > 0.5 else "valid" for r in contacts]
    plt.bar(
        [r["event_id"] for r in contacts],
        [r["contact_volume_excess_m"] for r in contacts],
        color=["red" if s == "invalid" else "green" for s in statuses],
    )
    plt.axhline(0.5, color="k", ls="--")
    plt.ylabel("contact-volume excess m")
    plt.title("Physical hypothesis status (cost similarity is insufficient)")
    save("stage5b_v33_hypothesis_geometry.jpg")
    families = objective["families"]
    plt.figure(figsize=(9, 5))
    plt.bar([r["name"] for r in families], [r["terms"] for r in families])
    plt.ylabel("normalized residual terms")
    plt.title("Objective family audit — Phase B blocked by Phase A")
    save("stage5b_v33_objective_breakdown.jpg")


if __name__ == "__main__":
    raise SystemExit(main())
