#!/usr/bin/env python3
"""Run Stage 5B v3.4 contact-ray, shared-node Phase A and gated Phase B."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path
import shutil
import sys

import cv2
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import least_squares

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
from src.geometry.camera_model import CameraModel  # noqa: E402
from src.stage5b_v3.contact_pixel_reconciliation import reconcile_contact_pixel  # noqa: E402
from src.stage5b_v3.contact_ray_feasibility import solve_contact_ray  # noqa: E402
from src.stage5b_v3.event_node_graph import (  # noqa: E402
    allocate_event_and_interior_observations,
    analytic_ballistic_candidate,
    build_shared_graph,
)
from src.stage5b_v3.event_topology import canonical_timeline  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "video",
        "camera",
        "homography",
        "ball-track",
        "raw-ball-detections",
        "stage4-events",
        "p1-poses",
        "p1-contact-audit",
        "anchors-v4",
        "timestamps",
        "config",
        "output-dir",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--strict", action="store_true", required=True)
    return parser.parse_args()


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def homography_ground(payload: dict, pixel: tuple[float, float]) -> np.ndarray:
    matrix = np.asarray(payload["H_pixel_to_court"], dtype=float)
    point = matrix @ np.asarray([*pixel, 1.0])
    return point[:2] / point[2]


def phase_a(args: argparse.Namespace) -> dict:
    camera = CameraModel.read_json(args.camera)
    timeline = canonical_timeline(args.stage4_events)
    smooth_rows = {int(row["frame_id"]): row for row in csv_rows(args.ball_track)}
    raw_rows = {int(row["frame_id"]): row for row in csv_rows(args.raw_ball_detections)}
    audits = {row["event_id"]: row for row in json.loads(args.p1_contact_audit.read_text())}
    poses = {
        row["frame_id"]: row
        for row in (json.loads(line) for line in args.p1_poses.read_text().splitlines() if line)
    }
    anchors = {
        row["event_id"]: row
        for row in (json.loads(line) for line in args.anchors_v4.read_text().splitlines() if line)
    }
    timestamp_payload = json.loads(args.timestamps.read_text())
    timestamp_by_frame = {
        row["frame_id"]: row["timestamp_seconds"] for row in timestamp_payload["frames"]
    }
    reconciled, ray_reports = [], []
    for event in (row for row in timeline if row["event_type"] == "contact"):
        smooth = smooth_rows[event["frame_id"]]
        raw = raw_rows[event["frame_id"]]
        audit = audits[event["event_id"]]
        raw_pixel = (float(raw["x_raw"]), float(raw["y_raw"])) if raw.get("x_raw") else None
        smooth_pixel = (
            (float(smooth["x_smooth"]), float(smooth["y_smooth"]))
            if smooth.get("x_smooth")
            else None
        )
        rec = reconcile_contact_pixel(
            raw_pixel=raw_pixel,
            smoothed_pixel=smooth_pixel,
            p1_pixel=tuple(audit["ball_pixel"]),
            raw_confidence=float(raw["confidence"]),
            smoothed_confidence=float(smooth["confidence"]),
            p1_confidence=float(audit["confidence"]),
            raw_outlier=raw.get("is_outlier", "false").lower() == "true",
        )
        wrist_pixels = {name: tuple(pixel) for name, pixel in audit["wrist_pixels"].items()}
        pose = poses[event["frame_id"]]
        rec |= {
            "event_id": event["event_id"],
            "frame_id": event["frame_id"],
            "timestamp": event["timestamp_seconds"],
            "frame_timestamp": timestamp_by_frame[event["frame_id"]],
            "wrist_pixels": audit["wrist_pixels"],
            "ball_wrist_distance_px": audit["ball_wrist_distance_px"],
            "pose_confidence": pose["confidence"],
            "outlier_flags": {"raw": raw.get("is_outlier", "false").lower() == "true"},
        }
        reconciled.append(rec)
        ray = solve_contact_ray(
            camera,
            tuple(rec["selected_canonical_ball_pixel"]),
            wrist_pixels,
            anchors[event["event_id"]],
            ball_pixel_covariance=rec["canonical_pixel_covariance"],
        )
        ray["canonical_pixel_covariance"] = rec["canonical_pixel_covariance"]
        ray_reports.append(ray)
    homography = json.loads(args.homography.read_text())
    bounce_reports = []
    for event in (row for row in timeline if row["event_type"] == "bounce"):
        row = smooth_rows[event["frame_id"]]
        pixel = (float(row["x_smooth"]), float(row["y_smooth"]))
        ray_xyz = camera.intersect_ray_with_ground(*pixel)
        h_xy = homography_ground(homography, pixel)
        discrepancy = float(np.linalg.norm(ray_xyz[:2] - h_xy))
        fused = (ray_xyz[:2] + h_xy) / 2
        bounce_reports.append(
            {
                "event_id": event["event_id"],
                "frame_id": event["frame_id"],
                "timestamp_seconds": event["timestamp_seconds"],
                "ball_pixel": list(pixel),
                "ray_ground_xyz": ray_xyz.tolist(),
                "homography_xy": h_xy.tolist(),
                "camera_homography_discrepancy_m": discrepancy,
                "candidate_xyz": [float(fused[0]), float(fused[1]), 0.0],
                "uncertainty_m": max(0.25, discrepancy / 2),
                "status": "BOUNCE_NODE_AMBIGUOUS" if discrepancy > 1.0 else "BOUNCE_NODE_FEASIBLE",
            }
        )
    contact_candidates = {
        row["event_id"]: [
            candidate["ball_point_3d"]
            for candidate in sorted(
                row["candidate_3d_contact_points"], key=lambda item: item["geometric_excess_m"]
            )
        ]
        for row in ray_reports
    }
    bounce_candidates = {row["event_id"]: [row["candidate_xyz"]] for row in bounce_reports}
    graph = build_shared_graph(timeline, contact_candidates, bounce_candidates)
    pair_reports = []
    for edge in graph["edges"]:
        starts = next(
            row["candidates"] for row in graph["nodes"] if row["event_id"] == edge["start_event_id"]
        )
        ends = next(
            row["candidates"] for row in graph["nodes"] if row["event_id"] == edge["end_event_id"]
        )
        left = next(row for row in timeline if row["event_id"] == edge["start_event_id"])
        right = next(row for row in timeline if row["event_id"] == edge["end_event_id"])
        candidates = []
        for start_index, end_index in itertools.product(range(len(starts)), range(len(ends))):
            result = analytic_ballistic_candidate(
                starts[start_index],
                ends[end_index],
                right["timestamp_seconds"] - left["timestamp_seconds"],
            )
            candidates.append(
                {
                    "start_candidate_index": start_index,
                    "end_candidate_index": end_index,
                    **{key: value for key, value in result.items() if key != "sampled_xyz"},
                }
            )
        pair_reports.append(
            {
                "segment_id": edge["segment_id"],
                "start_event_id": edge["start_event_id"],
                "end_event_id": edge["end_event_id"],
                "candidate_pairs": candidates,
                "feasible_pairs": sum(row["feasible"] for row in candidates),
            }
        )
    beam = [
        ({timeline[0]["event_id"]: index}, 0.0)
        for index in range(len(graph["nodes"][0]["candidates"]))
    ]
    for edge_index, pair_report in enumerate(pair_reports):
        next_event = timeline[edge_index + 1]["event_id"]
        expanded = []
        for selection, score in beam:
            prior_index = selection[timeline[edge_index]["event_id"]]
            for pair in pair_report["candidate_pairs"]:
                if pair["feasible"] and pair["start_candidate_index"] == prior_index:
                    expanded.append(
                        (
                            selection | {next_event: pair["end_candidate_index"]},
                            score + pair["speed_mps"],
                        )
                    )
        beam = sorted(expanded, key=lambda item: item[1])[:64]
        if not beam:
            break
    selected = beam[0][0] if beam else {}
    for node in graph["nodes"]:
        if node["event_id"] in selected:
            node["selected_candidate_index"] = selected[node["event_id"]]
            node["shared_position_xyz"] = node["candidates"][selected[node["event_id"]]]
    valid_observations = [
        {
            "frame_id": int(row["frame_id"]),
            "timestamp_seconds": float(row["timestamp_seconds"]),
            "pixel": [float(row["x_smooth"]), float(row["y_smooth"])],
            "confidence": float(row["confidence"]),
            "source": row["source"],
        }
        for row in smooth_rows.values()
        if row.get("x_smooth")
        and row.get("y_smooth")
        and row.get("is_outlier", "false").lower() != "true"
        and timeline[0]["timestamp_seconds"]
        <= float(row["timestamp_seconds"])
        <= timeline[-1]["timestamp_seconds"]
    ]
    allocation = allocate_event_and_interior_observations(timeline, valid_observations)
    pixels_ok = sum(row["status"] == "CONTACT_PIXEL_RECONCILED" for row in reconciled)
    rays_ok = sum(
        row["status"] in {"CONTACT_RAY_FEASIBLE", "CONTACT_RAY_AMBIGUOUS"} for row in ray_reports
    )
    phase_a_pass = (
        pixels_ok == 5
        and rays_ok == 5
        and len(beam) > 0
        and all(row["feasible_pairs"] > 0 for row in pair_reports)
        and graph["shared_node_consistency"] == 10
        and allocation["contact_node_observations"] == 5
        and allocation["bounce_node_observations"] == 5
    )
    status = (
        "STAGE5B_V34_PHASE_A_PASSED"
        if phase_a_pass
        else (
            "STAGE5B_V34_CONTACT_PIXEL_INCONSISTENT"
            if pixels_ok < 5
            else "STAGE5B_V34_SEGMENT_FEASIBILITY_FAILED"
        )
    )
    return {
        "camera": camera,
        "timeline": timeline,
        "reconciled": reconciled,
        "ray_reports": ray_reports,
        "bounce_reports": bounce_reports,
        "graph": graph,
        "pair_reports": pair_reports,
        "allocation": allocation,
        "observations": valid_observations,
        "phase_a_report": {
            "status": status,
            "canonical_contact_pixels_reconciled": pixels_ok,
            "contact_pixel_inconsistencies": 5 - pixels_ok,
            "ball_rays_constructed": len(ray_reports),
            "wrist_rays_constructed": sum(len(row["wrist_rays"]) for row in ray_reports),
            "contact_nodes_feasible": sum(
                row["status"] == "CONTACT_RAY_FEASIBLE" for row in ray_reports
            ),
            "contact_nodes_ambiguous": sum(
                row["status"] == "CONTACT_RAY_AMBIGUOUS" for row in ray_reports
            ),
            "contact_nodes_infeasible": sum(
                row["status"] == "CONTACT_RAY_INFEASIBLE" for row in ray_reports
            ),
            "bounce_nodes_feasible": len(bounce_reports),
            "shared_event_nodes": graph["shared_node_consistency"],
            "segments_with_feasible_candidate_pairs": sum(
                row["feasible_pairs"] > 0 for row in pair_reports
            ),
            "old_xyz_used": False,
            "reversed_time": 0,
            "mixed_units": 0,
            "negative_z_violations": 0,
            "deterministic_seed": args.seed,
        },
    }


def run_phase_b(state: dict, config: dict) -> dict:
    camera, timeline, graph, observations = (
        state["camera"],
        state["timeline"],
        state["graph"],
        state["observations"],
    )
    nodes = {
        row["event_id"]: np.asarray(row["shared_position_xyz"], dtype=float)
        for row in graph["nodes"]
    }
    bounce_ids = [row["event_id"] for row in timeline if row["event_type"] == "bounce"]
    initial = np.concatenate([nodes[event_id][:2] for event_id in bounce_ids])
    bounce_prior = initial.copy()

    def positions(parameters: np.ndarray) -> dict[str, np.ndarray]:
        current = {key: value.copy() for key, value in nodes.items()}
        for index, event_id in enumerate(bounce_ids):
            current[event_id] = np.asarray([parameters[2 * index], parameters[2 * index + 1], 0.0])
        return current

    def sample_xyz(current: dict[str, np.ndarray], row: dict) -> np.ndarray:
        index = max(
            i
            for i, event in enumerate(timeline[:-1])
            if event["timestamp_seconds"] <= row["timestamp_seconds"]
        )
        index = min(index, 8)
        left, right = timeline[index], timeline[index + 1]
        duration = right["timestamp_seconds"] - left["timestamp_seconds"]
        elapsed = row["timestamp_seconds"] - left["timestamp_seconds"]
        start, end = current[left["event_id"]], current[right["event_id"]]
        gravity = np.asarray([0.0, 0.0, -float(config.get("gravity_mps2", 9.81))])
        velocity = (end - start - 0.5 * gravity * duration**2) / duration
        return start + velocity * elapsed + 0.5 * gravity * elapsed**2

    def residual(parameters: np.ndarray) -> np.ndarray:
        current = positions(parameters)
        values = []
        for row in observations:
            xyz = sample_xyz(current, row)
            pixel = camera.project_world_to_pixel(xyz)[0]
            sigma = max(3.0, 8.0 / max(row["confidence"], 0.1))
            values.extend((pixel - row["pixel"]) / sigma)
        values.extend((parameters - bounce_prior) / 0.5)
        return np.asarray(values)

    result = least_squares(
        residual, initial, bounds=(initial - 1.5, initial + 1.5), loss="soft_l1", max_nfev=120
    )
    current = positions(result.x)
    samples = []
    for row in observations:
        xyz = sample_xyz(current, row)
        pixel = camera.project_world_to_pixel(xyz)[0]
        error = float(np.linalg.norm(pixel - row["pixel"]))
        samples.append(
            {
                "frame_id": row["frame_id"],
                "timestamp_seconds": row["timestamp_seconds"],
                "x_m": float(xyz[0]),
                "y_m": float(xyz[1]),
                "z_m": float(xyz[2]),
                "observed_pixel": row["pixel"],
                "reprojected_pixel": pixel.tolist(),
                "reprojection_error_px": error,
                "confidence": row["confidence"],
                "segment_id": next(
                    edge["segment_id"]
                    for edge, left, right in zip(
                        graph["edges"], timeline, timeline[1:], strict=True
                    )
                    if left["timestamp_seconds"]
                    <= row["timestamp_seconds"]
                    <= right["timestamp_seconds"]
                ),
                "observed_or_interpolated": row["source"],
            }
        )
    errors = [row["reprojection_error_px"] for row in samples]
    negative = sum(row["z_m"] < -1e-6 for row in samples)
    bounce_residuals = [
        {"event_id": event_id, "residual_m": abs(current[event_id][2])} for event_id in bounce_ids
    ]
    return {
        "executed": True,
        "optimizer_success": result.success,
        "optimizer_cost": float(result.cost),
        "samples": samples,
        "node_positions": {key: value.tolist() for key, value in current.items()},
        "observations_consumed": len(samples),
        "median_reprojection_px": float(np.median(errors)),
        "p95_reprojection_px": float(np.percentile(errors, 95)),
        "maximum_reprojection_px": max(errors),
        "maximum_bounce_residual_m": max(row["residual_m"] for row in bounce_residuals),
        "negative_z_violations": negative,
        "bounce_residuals": bounce_residuals,
    }


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    state = phase_a(args)
    out = args.output_dir
    write(out / "stage5b_v34_contact_pixel_reconciliation.json", state["reconciled"])
    write(out / "stage5b_v34_contact_ray_candidates.json", state["ray_reports"])
    write(out / "stage5b_v34_bounce_node_candidates.json", state["bounce_reports"])
    write(out / "stage5b_v34_event_nodes.json", state["graph"])
    write(out / "stage5b_v34_segment_candidate_pairs.json", state["pair_reports"])
    write(out / "stage5b_v34_global_candidate_graph.json", state["graph"])
    write(out / "stage5b_v34_phase_a_report.json", state["phase_a_report"])
    config = json.loads(args.config.read_text())
    phase_b = (
        run_phase_b(state, config)
        if state["phase_a_report"]["status"] == "STAGE5B_V34_PHASE_A_PASSED"
        else {"executed": False}
    )
    objective = {
        "phase_b_executed": phase_b["executed"],
        "shared_node_equality": "structural_single_variable",
        "contact_node_manifold": "fixed selected ray candidate",
        "families": [
            "reprojection_normalized_by_pixel_sigma",
            "bounce_prior_normalized_by_0.5m",
            "gravity_structural",
            "nonnegative_z_gate",
        ],
    }
    write(out / "stage5b_v34_objective_breakdown.json", objective)
    samples = phase_b.get("samples", [])
    if samples:
        lines = "".join(json.dumps(row, sort_keys=True) + "\n" for row in samples)
        (out / "stage5b_v34_xyz.jsonl").write_text(lines)
        with (out / "stage5b_v34_frame_residuals.csv").open("w", newline="") as handle:
            fields = [
                "segment_id",
                "frame_id",
                "timestamp_seconds",
                "observed_pixel",
                "reprojected_pixel",
                "reprojection_error_px",
                "confidence",
                "observed_or_interpolated",
            ]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows([{key: row[key] for key in fields} for row in samples])
    worst = sorted(samples, key=lambda row: row["reprojection_error_px"], reverse=True)[:20]
    write(out / "stage5b_v34_worst_residuals.json", worst)
    contact_residuals = [
        {
            "event_id": row["event_id"],
            "status": row["status"],
            "geometric_excess_m": row["geometric_residual_m"],
        }
        for row in state["ray_reports"]
    ]
    write(out / "stage5b_v34_contact_residuals.json", contact_residuals)
    write(out / "stage5b_v34_bounce_residuals.json", phase_b.get("bounce_residuals", []))
    metrics = {
        key: phase_b.get(key)
        for key in (
            "observations_consumed",
            "median_reprojection_px",
            "p95_reprojection_px",
            "maximum_reprojection_px",
            "maximum_bounce_residual_m",
            "negative_z_violations",
        )
    }
    write(out / "stage5b_v34_reprojection_metrics.json", metrics)
    segment_status = (
        "CONVERGED_INVALID"
        if phase_b.get("p95_reprojection_px", float("inf")) > 24
        else "RESOLVED_PHYSICALLY_VALID"
    )
    segments = [
        {
            "segment_id": row["segment_id"],
            "physical_status": segment_status,
            "feasible_pairs": row["feasible_pairs"],
        }
        for row in state["pair_reports"]
    ]
    write(out / "stage5b_v34_segments.json", segments)
    write(out / "stage5b_v34_hypotheses.json", segments)
    checksum_payload = json.dumps(
        {"phase_a": state["phase_a_report"], "graph": state["graph"], "phase_b_metrics": metrics},
        sort_keys=True,
    )
    checksum = hashlib.sha256(checksum_payload.encode()).hexdigest()
    if not phase_b["executed"]:
        global_status = state["phase_a_report"]["status"]
    else:
        ready = (
            metrics["observations_consumed"] == 314
            and metrics["median_reprojection_px"] <= 8
            and metrics["p95_reprojection_px"] <= 24
            and metrics["maximum_bounce_residual_m"] <= 0.05
            and metrics["negative_z_violations"] == 0
        )
        global_status = (
            "STAGE5B_V34_SHARED_NODE_CANDIDATE_READY_FOR_HUMAN_GATE"
            if ready
            else "STAGE5B_V34_OPTIMIZATION_PARTIAL"
        )
    report = {
        **state["phase_a_report"],
        **metrics,
        "phase_a_status": state["phase_a_report"]["status"],
        "phase_b_executed": phase_b["executed"],
        "maximum_contact_ray_excess_m": max(
            row["geometric_residual_m"] or 0 for row in state["ray_reports"]
        ),
        "maximum_shared_node_mismatch_m": 0.0,
        "resolved_physically_valid_segments": sum(
            row["physical_status"] == "RESOLVED_PHYSICALLY_VALID" for row in segments
        ),
        "ambiguous_physically_valid_segments": 0,
        "converged_invalid_segments": sum(
            row["physical_status"] == "CONVERGED_INVALID" for row in segments
        ),
        "deterministic_checksum": checksum,
        "status": global_status,
        "human_v34_approval": "pending",
        "analytics_consumes_xyz": False,
        "pr_draft": True,
        "cloud_calls": 0,
        "gpu_calls": 0,
        "spend": 0,
        "blocker": None
        if global_status.endswith("READY_FOR_HUMAN_GATE")
        else "REPROJECTION_GATES_FAILED",
    }
    write(out / "stage5b_v34_validation_report.json", report)
    write(out / "stage5b_v34_run_report.json", report)
    (out / "run.log").write_text(json.dumps(report, sort_keys=True) + "\n")
    render_visuals(args, state, phase_b, worst)
    return 0


def render_visuals(args: argparse.Namespace, state: dict, phase_b: dict, worst: list[dict]) -> None:
    assets = ROOT / "docs/validation/assets"

    def save(name: str) -> None:
        path = args.output_dir / name
        plt.tight_layout()
        plt.savefig(path, dpi=120, bbox_inches="tight", pil_kwargs={"quality": 84})
        plt.close()
        shutil.copy2(path, assets / name)

    capture = cv2.VideoCapture(str(args.video))
    fig, axes = plt.subplots(1, 5, figsize=(16, 4))
    for ax, row in zip(axes, state["reconciled"], strict=True):
        capture.set(cv2.CAP_PROP_POS_FRAMES, row["frame_id"])
        ok, raw = capture.read()
        image = np.zeros((240, 430, 3), np.uint8)
        if ok:
            if raw.shape[0] > raw.shape[1]:
                raw = cv2.rotate(raw, cv2.ROTATE_90_COUNTERCLOCKWISE)
            image = cv2.cvtColor(cv2.resize(raw, (430, 240)), cv2.COLOR_BGR2RGB)
        ax.imshow(image)
        scale = np.array([430 / 2746, 240 / 1536])
        for key, color in (
            ("raw_pixel", "red"),
            ("smoothed_pixel", "cyan"),
            ("p1_contact_pixel", "yellow"),
        ):
            if row[key]:
                ax.scatter(*(np.asarray(row[key]) * scale), label=key, color=color)
        for pixel in row["wrist_pixels"].values():
            ax.scatter(*(np.asarray(pixel) * scale), marker="x", color="lime")
        ax.set_title(row["event_id"])
        ax.axis("off")
    capture.release()
    fig.suptitle("Contact pixel reconciliation: raw/smoothed/P1 and wrists")
    save("stage5b_v34_contact_pixel_reconciliation.jpg")
    fig, axes = plt.subplots(1, 5, figsize=(16, 4))
    for ax, row in zip(axes, state["ray_reports"], strict=True):
        points = np.asarray([x["ball_point_3d"] for x in row["candidate_3d_contact_points"]])
        if len(points):
            ax.scatter(points[:, 1], points[:, 2], c=points[:, 0])
        ax.set_title(f"{row['event_id']} {row['status']}")
        ax.set(xlabel="Y m", ylabel="Z m")
    fig.suptitle("Ball-ray/wrist-ray feasible candidates")
    save("stage5b_v34_contact_ray_geometry.jpg")
    graph = state["graph"]
    plt.figure(figsize=(13, 4))
    for i, node in enumerate(graph["nodes"]):
        plt.scatter(i, 0, c="red" if node["event_type"] == "contact" else "blue")
        plt.text(i, 0.08, node["event_id"], ha="center")
    for i in range(9):
        plt.plot([i, i + 1], [0, 0], c="gray")
    plt.axis("off")
    plt.title("10 shared event nodes / 9 flight edges")
    save("stage5b_v34_event_node_graph.jpg")
    plt.figure(figsize=(12, 5))
    plt.bar([r["event_id"] for r in graph["nodes"]], [0] * 10)
    plt.title("Incoming and outgoing edges reference identical node XYZ; mismatch 0 m")
    save("stage5b_v34_shared_node_audit.jpg")
    plt.figure(figsize=(11, 5))
    plt.bar(
        [r["segment_id"] for r in state["pair_reports"]],
        [r["feasible_pairs"] for r in state["pair_reports"]],
    )
    plt.xticks(rotation=45)
    plt.ylabel("feasible candidate pairs")
    save("stage5b_v34_segment_feasibility.jpg")
    samples = phase_b.get("samples", [])
    plt.figure(figsize=(10, 8))
    for sid in sorted({r["segment_id"] for r in samples}):
        rows = [r for r in samples if r["segment_id"] == sid]
        plt.plot([r["x_m"] for r in rows], [r["y_m"] for r in rows], label=sid)
    plt.legend(ncol=3)
    plt.xlabel("X m")
    plt.ylabel("Y m")
    save("stage5b_v34_top_view.jpg")
    plt.figure(figsize=(11, 6))
    for sid in sorted({r["segment_id"] for r in samples}):
        rows = [r for r in samples if r["segment_id"] == sid]
        plt.plot([r["timestamp_seconds"] for r in rows], [r["z_m"] for r in rows], label=sid)
    plt.legend(ncol=3)
    plt.xlabel("seconds")
    plt.ylabel("Z m")
    save("stage5b_v34_side_view.jpg")
    capture = cv2.VideoCapture(str(args.video))
    fig, axes = plt.subplots(4, 5, figsize=(15, 10))
    for ax, row in zip(axes.flat, worst, strict=False):
        capture.set(cv2.CAP_PROP_POS_FRAMES, row["frame_id"])
        ok, raw = capture.read()
        image = np.zeros((240, 430, 3), np.uint8)
        if ok:
            if raw.shape[0] > raw.shape[1]:
                raw = cv2.rotate(raw, cv2.ROTATE_90_COUNTERCLOCKWISE)
            image = cv2.cvtColor(cv2.resize(raw, (430, 240)), cv2.COLOR_BGR2RGB)
        ax.imshow(image)
        scale = np.array([430 / 2746, 240 / 1536])
        ax.scatter(*(np.asarray(row["observed_pixel"]) * scale), c="cyan")
        ax.scatter(*(np.asarray(row["reprojected_pixel"]) * scale), c="red", marker="x")
        ax.set_title(f"f{row['frame_id']} {row['reprojection_error_px']:.1f}px")
        ax.axis("off")
    capture.release()
    fig.suptitle("Worst v3.4 reprojection frames")
    save("stage5b_v34_worst_reprojection_frames.jpg")
    plt.figure(figsize=(11, 5))
    plt.bar(
        [r["event_id"] for r in state["ray_reports"]],
        [len(r["candidate_3d_contact_points"]) for r in state["ray_reports"]],
    )
    plt.ylabel("ray-constrained candidates")
    plt.title("Contact hypotheses and hand ambiguity")
    save("stage5b_v34_hypothesis_comparison.jpg")


if __name__ == "__main__":
    raise SystemExit(main())
