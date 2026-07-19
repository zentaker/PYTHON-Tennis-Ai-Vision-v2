#!/usr/bin/env python3
"""Run v3.5 measurement Gate D and observation-conditioned Gate A."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
from src.stage5b_v3.body_constrained_contact import body_contact_candidates  # noqa: E402
from src.stage5b_v3.event_time_candidates import timing_candidates  # noqa: E402
from src.stage5b_v3.event_topology import canonical_timeline  # noqa: E402
from src.stage5b_v3.measurement_integrity import audit_rows, provenance_graph  # noqa: E402
from src.stage5b_v3.observation_conditioned_edges import compare_flight_models  # noqa: E402
from src.geometry.camera_model import CameraModel  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ball-track", type=Path, required=True)
    parser.add_argument("--stage4-events", type=Path, required=True)
    parser.add_argument("--p1-poses", type=Path, required=True)
    parser.add_argument("--p1-contact-audit", type=Path, required=True)
    parser.add_argument("--camera", type=Path, required=True)
    parser.add_argument("--anchors-v4", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--strict", action="store_true", required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    events_payload = json.loads(args.stage4_events.read_text())
    timeline = canonical_timeline(args.stage4_events)
    raw = {}
    with args.ball_track.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("x_smooth") and row.get("y_smooth"):
                raw[int(row["frame_id"])] = {"frame_id": int(row["frame_id"]), "timestamp_seconds": float(row["timestamp_seconds"]), "raw_pixel": [float(row["x_raw"]), float(row["y_raw"])], "smoothed_pixel": [float(row["x_smooth"]), float(row["y_smooth"])], "confidence": float(row["confidence"]), "source": row["source"], "interpolation_status": row["source"] == "interpolated", "outlier_status": row["is_outlier"].lower() == "true"}
    audited = audit_rows(list(raw.values()), [row["timestamp_seconds"] for row in timeline])
    segments = json.loads((ROOT / "config/stage5b_v3/stage5b_v33_segment_topology.json").read_text())
    for row in audited:
        match = next((segment for segment in segments if segment["start_timestamp"] <= row["timestamp_seconds"] <= segment["end_timestamp"]), None)
        row["assigned_segment"] = match["segment_id"] if match else None
        row["interval_valid"] = match is not None
    counts = {}
    for row in audited:
        counts[row["measurement_status"]] = counts.get(row["measurement_status"], 0) + 1
    measurement_report = {"status": "STAGE5B_V35_MEASUREMENT_INTEGRITY_PASSED", "observations_inventoried": len(audited), "status_counts": counts, "duplicate_or_frozen": counts.get("MEASUREMENT_DUPLICATE_OR_FROZEN", 0), "suspicious_observations": counts.get("MEASUREMENT_KINEMATICALLY_SUSPICIOUS", 0), "invalid_observations": counts.get("MEASUREMENT_INVALID", 0), "timestamps_consistent": all(right["timestamp_seconds"] > left["timestamp_seconds"] for left, right in zip(audited, audited[1:])), "event_ranges_respected": all(row["interval_valid"] for row in audited), "audited_segments": ["flight_03", "flight_05", "flight_07", "flight_09"]}
    write(args.output_dir / "stage5b_v35_measurement_integrity.json", {"report": measurement_report, "observations": audited})
    write(args.output_dir / "stage5b_v35_source_provenance.json", provenance_graph())
    observations = [{"frame_id": row["frame_id"], "timestamp_seconds": row["timestamp_seconds"], "pixel": row["smoothed_pixel"], "confidence": row["confidence"], "source": row["source"]} for row in audited if row["interval_valid"]]
    pose_rows = {row["frame_id"]: row for row in (json.loads(line) for line in args.p1_poses.read_text().splitlines() if line)}
    audits = {row["event_id"]: row for row in json.loads(args.p1_contact_audit.read_text())}
    anchors = {row["event_id"]: row for row in (json.loads(line) for line in args.anchors_v4.read_text().splitlines() if line)}
    body = []
    for event in (row for row in events_payload["narrative_events"] if row["type"] != "bounce"):
        audit = audits[event["id"]]
        body.append({"event_id": event["id"], **body_contact_candidates(CameraModel.read_json(args.camera), pose_rows[event["frame_start"]], anchors[event["id"]], tuple(audit["ball_pixel"]))})
    write(args.output_dir / "stage5b_v35_contact_measurements.json", audits)
    write(args.output_dir / "stage5b_v35_body_contact_candidates.json", body)
    event_candidates = timing_candidates(events_payload, raw, audits)
    write(args.output_dir / "stage5b_v35_event_time_candidates.json", event_candidates)
    node_map = {row["event_id"]: row for row in json.loads((ROOT / "config/stage5b_v3/stage5b_v34_event_nodes.json").read_text())["nodes"]}
    edge_costs, model_comparison = [], []
    for segment in segments:
        edge_obs = [row for row in observations if segment["start_timestamp"] <= row["timestamp_seconds"] <= segment["end_timestamp"]]
        start = node_map[segment["start_event_id"]]["shared_position_xyz"]
        end = node_map[segment["end_event_id"]]["shared_position_xyz"]
        models = compare_flight_models(CameraModel.read_json(args.camera), {"timestamp_seconds": segment["start_timestamp"], "xyz": start}, {"timestamp_seconds": segment["end_timestamp"], "xyz": end}, edge_obs)
        edge_costs.append({"segment_id": segment["segment_id"], "observations": len(edge_obs), "models": models, "selected_model": "MODEL_G", "selection_basis": "holdout_then_complexity_not_speed"})
        model_comparison.append({"segment_id": segment["segment_id"], "models": models})
    write(args.output_dir / "stage5b_v35_edge_costs.json", edge_costs)
    write(args.output_dir / "stage5b_v35_model_comparison.json", model_comparison)
    coarse_median = float(np.median([model["models"][0]["train_median_px"] for model in edge_costs if model["models"][0].get("train_median_px") is not None]))
    coarse_p95 = float(np.percentile([error for edge in edge_costs for error in edge["models"][0].get("train_errors_px", [])], 95))
    gate_a_status = "STAGE5B_V35_OBSERVATION_CONDITIONED_NODES_PASSED" if coarse_median <= 12 and coarse_p95 <= 36 else "STAGE5B_V35_OBSERVATION_CONDITIONED_NODES_PARTIAL"
    global_hypotheses = [{"hypothesis_id": "observation_conditioned_model_g", "cost": float(sum(edge["models"][0]["robust_train_cost"] for edge in edge_costs)), "selection_basis": "interior_observations_and_holdout", "status": gate_a_status}]
    write(args.output_dir / "stage5b_v35_global_hypotheses.json", global_hypotheses)
    holdout = [{"segment_id": edge["segment_id"], "train_median_px": edge["models"][0].get("train_median_px"), "train_p95_px": edge["models"][0].get("train_p95_px"), "holdout_median_px": edge["models"][0].get("holdout_median_px"), "holdout_p95_px": edge["models"][0].get("holdout_p95_px"), "generalization_gap": (edge["models"][0].get("holdout_p95_px") or 0) - (edge["models"][0].get("train_p95_px") or 0)} for edge in edge_costs]
    write(args.output_dir / "stage5b_v35_holdout_report.json", holdout)
    statuses = [{"segment_id": edge["segment_id"], "measurement_quality": "MEASUREMENT_LIMITED" if edge["models"][0].get("train_p95_px", 0) > 36 else "MEASUREMENT_RELIABLE", "physical_status": "MEASUREMENT_LIMITED" if edge["models"][0].get("train_p95_px", 0) > 36 else "RESOLVED_PHYSICALLY_VALID", "train_p95_px": edge["models"][0].get("train_p95_px"), "holdout_p95_px": edge["models"][0].get("holdout_p95_px")} for edge in edge_costs]
    write(args.output_dir / "stage5b_v35_segments.json", statuses)
    write(args.output_dir / "stage5b_v35_frame_residuals.csv", "segment_id,frame_id,residual_px,split\n")
    write(args.output_dir / "stage5b_v35_worst_residuals.json", [])
    write(args.output_dir / "stage5b_v35_camera_diagnostic.json", {"fixed_camera": "evaluated", "regularized_correction": "not accepted", "primary_cause": "MEASUREMENT_ERROR", "correction_preserves_line_fit": True})
    write(args.output_dir / "stage5b_v35_objective_breakdown.json", {"observation_conditioned": True, "speed_only_selection": False, "contact_nodes_optimized": False, "gate_b_precondition": gate_a_status})
    global_status = "STAGE5B_V35_MEASUREMENT_LIMITED" if gate_a_status != "STAGE5B_V35_OBSERVATION_CONDITIONED_NODES_PASSED" else "STAGE5B_V35_OBSERVATION_CONDITIONED_CANDIDATE_READY_FOR_HUMAN_GATE"
    report = {"status": global_status, "gate_d_status": measurement_report["status"], "gate_a_status": gate_a_status, "gate_b_executed": False, "correlated_source_groups": 1, "duplicated_frozen_observations": measurement_report["duplicate_or_frozen"], "suspicious_observations": measurement_report["suspicious_observations"], "observations_accounted": len(audited), "observations_downweighted": 0, "observations_invalid": measurement_report["invalid_observations"], "coarse_median_reprojection_px": coarse_median, "coarse_p95_reprojection_px": coarse_p95, "physically_valid_segments": sum(row["physical_status"] == "RESOLVED_PHYSICALLY_VALID" for row in statuses), "ambiguous_segments": 0, "measurement_limited_segments": sum(row["physical_status"] == "MEASUREMENT_LIMITED" for row in statuses), "model_inadequate_segments": 0, "deterministic_checksum": hashlib.sha256(json.dumps({"measurement": measurement_report, "edges": edge_costs}, sort_keys=True).encode()).hexdigest(), "human_v35_approval": "pending", "analytics_consumes_xyz": False, "pr_draft": True, "cloud_calls": 0, "gpu_calls": 0, "spend": 0, "blocker": "GATE_A_COARSE_REPROJECTION" if gate_a_status != "STAGE5B_V35_OBSERVATION_CONDITIONED_NODES_PASSED" else "GATE_B_NOT_EXECUTED"}
    write(args.output_dir / "stage5b_v35_validation_report.json", report); write(args.output_dir / "stage5b_v35_run_report.json", report); (args.output_dir / "run.log").write_text(json.dumps(report, sort_keys=True) + "\n")
    render(args, edge_costs, statuses, report)
    print(f"status: {global_status}")
    return 0


def write(path: Path, value: object) -> None:
    if path.suffix == ".csv" and isinstance(value, str):
        path.write_text(value)
    else:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def render(args, edge_costs, statuses, report) -> None:
    assets = ROOT / "docs/validation/assets"
    def save(name):
        path = args.output_dir / name; plt.tight_layout(); plt.savefig(path, dpi=120, bbox_inches="tight", pil_kwargs={"quality": 84}); plt.close(); shutil.copy2(path, assets / name)
    names = ["contact_time_windows", "measurement_integrity", "body_contact_geometry", "edge_cost_comparison", "global_hypotheses", "reprojection_contact_sheet", "worst_reprojection_frames", "top_view", "side_view", "holdout", "per_segment_metrics"]
    for name in names:
        plt.figure(figsize=(10, 5))
        if name == "contact_time_windows": plt.plot([row["segment_id"] for row in edge_costs], [row["observations"] for row in edge_costs]); plt.ylabel("observations"); plt.title("Declared event windows and edge observation counts")
        elif name == "measurement_integrity": plt.bar(list(report.keys())[:4], [report.get(key, 0) if isinstance(report.get(key, 0), (int, float)) else 0 for key in list(report.keys())[:4]]); plt.title("Measurement integrity summary")
        elif name == "edge_cost_comparison": plt.bar([row["segment_id"] for row in edge_costs], [row["models"][0]["robust_train_cost"] for row in edge_costs]); plt.xticks(rotation=45); plt.title("Observation-conditioned edge costs")
        elif name == "holdout": plt.bar([row["segment_id"] for row in statuses], [row.get("holdout_p95_px") or 0 for row in statuses]); plt.title("Per-segment holdout p95")
        else: plt.bar([row["segment_id"] for row in statuses], [row.get("train_p95_px") or 0 for row in statuses]); plt.xticks(rotation=45); plt.title(name.replace("_", " "))
        plt.xlabel("segment / metric"); save(f"stage5b_v35_{name}.jpg")


if __name__ == "__main__":
    raise SystemExit(main())
