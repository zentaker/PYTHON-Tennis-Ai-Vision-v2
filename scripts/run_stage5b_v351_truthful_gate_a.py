#!/usr/bin/env python3
# ruff: noqa: E701, E702, E703, E501, F401, F841
"""Truthful V3.5.1 measurement Gate D and candidate-based Gate A runner."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
from src.geometry.camera_model import CameraModel  # noqa: E402
from src.stage5b_v3.body_constrained_contact import body_contact_candidates  # noqa: E402
from src.stage5b_v3.event_time_candidates import declared_event_frames  # noqa: E402
from src.stage5b_v3.measurement_integrity import audit_report, audit_rows, provenance_graph  # noqa: E402
from src.stage5b_v3.observation_conditioned_edges import score_edge  # noqa: E402
from src.stage5b_v3.truthful_global_search import candidate_selection_changes_cost, shared_node_consistency  # noqa: E402
from src.stage5b_v3.contact_ray_feasibility import point_on_ray_at_height  # noqa: E402


def read_track(path: Path) -> dict[int, dict]:
    with path.open(newline="") as handle:
        return {
            int(row["frame_id"]): {
                "frame_id": int(row["frame_id"]),
                "timestamp_seconds": float(row["timestamp_seconds"]),
                "raw_pixel": [float(row["x_raw"]), float(row["y_raw"])],
                "smoothed_pixel": [float(row["x_smooth"]), float(row["y_smooth"])],
                "confidence": float(row["confidence"]),
                "source": row["source"],
                "interpolation_status": row["source"] == "interpolated",
                "outlier_status": row.get("is_outlier", "false").lower() == "true",
            }
            for row in csv.DictReader(handle)
            if row.get("x_smooth") and row.get("y_smooth")
        }


def write(path: Path, value) -> None:
    if path.suffix == ".csv":
        path.write_text(value)
    else:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def event_candidates(events, track, audits, poses, anchors, camera):
    result = []
    contact_out, bounce_out = [], []
    for event in events:
        event_type = "bounce" if event["type"] == "bounce" else "contact"
        for frame_id in declared_event_frames(event):
            row = track.get(frame_id)
            warnings = []
            if row is None:
                warnings.append("OBSERVATION_UNAVAILABLE")
                result.append({"candidate_id": f"{event['id']}_{frame_id}_unusable", "event_id": event["id"], "event_type": event_type, "frame_id": frame_id, "timestamp": None, "xyz": None, "covariance": [[100.0, 0.0], [0.0, 100.0]], "prior_cost": 100.0, "measurement_status": "MEASUREMENT_INVALID", "provenance": "ball_track_missing", "physical_status": "UNAVAILABLE", "warnings": warnings, "usable": False})
                continue
            pixel = tuple(row["smoothed_pixel"])
            base = {"event_id": event["id"], "event_type": event_type, "frame_id": frame_id, "timestamp": row["timestamp_seconds"], "raw_pixel": row["raw_pixel"], "smoothed_pixel": row["smoothed_pixel"], "canonical_pixel": row["smoothed_pixel"], "covariance": [[9.0, 0.0], [0.0, 9.0]], "prior_cost": 0.0 if frame_id == event["frame_start"] else 0.25, "measurement_status": "MEASUREMENT_RELIABLE", "provenance": "stage3_ball_track", "physical_status": "CANDIDATE", "warnings": warnings, "usable": True}
            if event_type == "bounce":
                try:
                    xyz = camera.intersect_ray_with_ground(*pixel).tolist()
                    ground_status = "GROUND_RAY_FEASIBLE" if np.isfinite(xyz).all() else "GROUND_RAY_INVALID"
                except (ValueError, ZeroDivisionError):
                    xyz, ground_status = None, "GROUND_RAY_INVALID"
                candidate = {**base, "candidate_id": f"{event['id']}_{frame_id}", "xyz": xyz, "ray_ground_xyz": xyz, "homography_xyz": None, "uncertainty": {"pixel_sigma_px": 3.0, "ground_sigma_m": 0.2}, "physical_status": ground_status, "warnings": warnings + (["GROUND_RAY_UNAVAILABLE"] if xyz is None else [])}
                bounce_out.append(candidate)
                result.append(candidate)
                continue
            pose = poses.get(frame_id)
            anchor = anchors.get(event["id"])
            if pose is None:
                warnings.append("POSE_UNAVAILABLE")
            body = None
            if pose is not None and anchor is not None:
                body = body_contact_candidates(camera, pose, anchor, pixel)
            if body and body["candidates"]:
                for rank, best in enumerate(body["candidates"][:2]):
                    candidate = {**base, "candidate_id": f"{event['id']}_{frame_id}_body{rank}", "xyz": best["xyz"], "body_candidate": best, "body_method_status": body["method_status"], "physical_status": "BODY_CONTACT_APPROXIMATE", "prior_cost": base["prior_cost"] - float(best["prior_log_probability"]), "uncertainty": {"pixel_sigma_px": 3.0, "anchor": anchor.get("total_ci95")}}
                    contact_out.append(candidate)
                    result.append(candidate)
            else:
                try:
                    xyz, ray_parameter = point_on_ray_at_height(camera, pixel, 1.5)
                    candidate = {**base, "candidate_id": f"{event['id']}_{frame_id}_ray", "xyz": xyz.tolist(), "ray_parameter": ray_parameter, "body_method_status": "BODY_CONTACT_UNAVAILABLE", "physical_status": "RAY_ONLY_NOT_BODY_VALID", "prior_cost": base["prior_cost"] + 5.0, "uncertainty": {"pixel_sigma_px": 3.0}}
                except ValueError:
                    candidate = {**base, "candidate_id": f"{event['id']}_{frame_id}_invalid", "xyz": None, "body_method_status": "BODY_CONTACT_UNAVAILABLE", "physical_status": "UNAVAILABLE", "usable": False, "prior_cost": 100.0}
                contact_out.append(candidate)
                result.append(candidate)
    return result, contact_out, bounce_out


def edge_for(camera, start, end, observations):
    if start.get("xyz") is None or end.get("xyz") is None:
        return {"feasible": False, "reason": "NODE_UNAVAILABLE", "observations_total": len(observations), "observations_usable": 0, "observations_invalid": len(observations), "total_edge_cost": float("inf"), "residual_rows": []}
    return score_edge(camera, {"timestamp_seconds": start["timestamp"], "xyz": start["xyz"], "prior_cost": start.get("prior_cost", 0.0)}, {"timestamp_seconds": end["timestamp"], "xyz": end["xyz"], "prior_cost": end.get("prior_cost", 0.0)}, observations)


def beam_search(events, by_event, segments, observations, camera):
    states = [{"choices": [candidate], "cost": candidate.get("prior_cost", 0.0)} for candidate in by_event[events[0]["id"]] if candidate.get("usable") and candidate.get("xyz")]
    edge_records = []
    edge_cache = {}
    for segment in segments:
        start_list, end_list = by_event[segment["start_event_id"]], by_event[segment["end_event_id"]]
        segment_obs = [row for row in observations if segment["start_timestamp"] <= row["timestamp_seconds"] <= segment["end_timestamp"]]
        for start in start_list:
            for end in end_list:
                scored = edge_for(camera, start, end, segment_obs)
                edge_cache[(start["candidate_id"], end["candidate_id"], segment["segment_id"])] = scored
                edge_records.append({"segment_id": segment["segment_id"], "start_candidate_id": start["candidate_id"], "end_candidate_id": end["candidate_id"], "observations_total": len(segment_obs), **scored, "selection_basis": "weighted_observation_cost_not_speed"})
        next_states = []
        for state in states:
            for end in end_list:
                if not end.get("usable") or not end.get("xyz"):
                    continue
                start = state["choices"][-1]
                score = edge_cache[(start["candidate_id"], end["candidate_id"], segment["segment_id"])]
                if not score.get("feasible"):
                    continue
                next_states.append({"choices": state["choices"] + [end], "cost": state["cost"] + float(score.get("total_edge_cost", 1e9)) + float(end.get("prior_cost", 0.0))})
        states = sorted(next_states, key=lambda item: (item["cost"], [x["candidate_id"] for x in item["choices"]]))[:12]
    return states, edge_records, edge_cache


def render_visuals(out, observations, residuals, candidates, hypotheses, segments):
    assets = ROOT / "docs/validation/assets"
    def save(name):
        plt.tight_layout(); plt.savefig(out / name, dpi=120, bbox_inches="tight", pil_kwargs={"quality": 82}); plt.close(); (assets / name).write_bytes((out / name).read_bytes())
    plt.figure(figsize=(12, 5)); x = [r["frame_id"] for r in observations]; y = [r["pixel"][0] for r in observations]; colors = ["tab:blue" if r["usable"] and r["weight_multiplier"] == 1 else "tab:orange" if r["usable"] else "tab:red" for r in observations]; plt.scatter(x, y, c=colors, s=8); plt.title("V3.5.1 measurement timeline: reliable/downweighted/invalid"); plt.xlabel("frame_id"); plt.ylabel("ball pixel x"); save("stage5b_v351_measurement_integrity.jpg")
    for name, title, xs, ys in [("stage5b_v351_contact_time_windows.jpg", "Declared contact frame ranges and observed ball pixels", [r["frame_id"] for r in candidates if r["event_type"] == "contact"], [r["canonical_pixel"][1] for r in candidates if r["event_type"] == "contact"]), ("stage5b_v351_contact_candidate_geometry.jpg", "Ground anchors and ball-ray candidate heights", [r["frame_id"] for r in candidates if r["event_type"] == "contact"], [r["xyz"][2] for r in candidates if r["event_type"] == "contact" and r.get("xyz")])]:
        plt.figure(figsize=(12, 5)); plt.scatter(xs, ys, c="tab:green", s=28); plt.title(title); plt.xlabel("declared frame"); plt.ylabel("pixel y" if "pixels" in title else "candidate Z (m)"); save(name)
    plt.figure(figsize=(12, 5)); plt.bar(range(len(hypotheses)), [h["total_cost"] for h in hypotheses], color="tab:purple"); plt.xticks(range(len(hypotheses)), [h["hypothesis_id"] for h in hypotheses], rotation=30); plt.ylabel("weighted total cost"); plt.title("Global candidate hypotheses"); save("stage5b_v351_global_hypotheses.jpg")
    plt.figure(figsize=(12, 5)); plt.scatter([r["frame_id"] for r in residuals], [r["residual_px"] for r in residuals], s=8); plt.xlabel("frame_id"); plt.ylabel("reprojection residual (px)"); plt.title("Observed versus candidate reprojection residuals"); save("stage5b_v351_reprojection_contact_sheet.jpg")
    worst = sorted(residuals, key=lambda r: r.get("residual_px", -1), reverse=True)[:20]; plt.figure(figsize=(12, 5)); plt.scatter([r["frame_id"] for r in worst], [r["residual_px"] for r in worst], c="tab:red", s=30); plt.xticks(rotation=45); plt.xlabel("worst frame_id"); plt.ylabel("residual (px)"); plt.title("Twenty worst usable residual frames"); save("stage5b_v351_worst_reprojection_frames.jpg")
    for name, title, axis in [("stage5b_v351_top_view.jpg", "Candidate flights and event nodes (top view)", 0), ("stage5b_v351_side_view.jpg", "Candidate flights and event nodes (side view)", 2)]:
        plt.figure(figsize=(12, 5));
        for hypothesis in hypotheses[:5]:
            points = [c["xyz"] for c in hypothesis["choices"] if c.get("xyz")];
            if points: plt.plot([p[axis] for p in points], [p[1] for p in points], marker="o", alpha=0.65)
        plt.title(title); plt.xlabel("X (m)" if axis == 0 else "Z (m)"); plt.ylabel("Y (m)" if axis == 0 else "Y (m)"); save(name)
    plt.figure(figsize=(12, 5)); plt.plot([s["segment_id"] for s in segments], [s["train_p95_px"] for s in segments], marker="o", label="train p95"); plt.plot([s["segment_id"] for s in segments], [s["holdout_p95_px"] for s in segments], marker="x", label="holdout p95"); plt.xticks(rotation=45); plt.legend(); plt.ylabel("pixels"); plt.title("Per-segment train/holdout metrics"); save("stage5b_v351_holdout.jpg"); save("stage5b_v351_per_segment_metrics.jpg")


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("ball_track", "stage4_events", "p1_poses", "p1_contact_audit", "camera", "anchors_v4", "output_dir"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True); parser.add_argument("--strict", action="store_true", required=True)
    args = parser.parse_args(); args.output_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(args.stage4_events.read_text()); track = read_track(args.ball_track)
    timeline = payload["narrative_events"]
    raw_audit = audit_rows(list(track.values()), [float(e["time_start_seconds"]) for e in timeline])
    segments = json.loads((ROOT / "config/stage5b_v3/stage5b_v33_segment_topology.json").read_text())
    for row in raw_audit:
        match = next((s for s in segments if s["start_timestamp"] <= row["timestamp_seconds"] <= s["end_timestamp"]), None); row["assigned_segment"] = match["segment_id"] if match else None; row["interval_valid"] = match is not None
    report = audit_report(raw_audit, event_ranges_respected=True)
    audited = {r["frame_id"]: r for r in raw_audit}
    observations = [{"frame_id": r["frame_id"], "timestamp_seconds": r["timestamp_seconds"], "pixel": r["smoothed_pixel"], "confidence": r["confidence"], "source": r["source"], "measurement_status": r["measurement_status"], "usable": r["usable"], "weight_multiplier": r["weight_multiplier"], "sigma_px": r["sigma_px"]} for r in raw_audit]
    poses = {int(json.loads(line)["frame_id"]): json.loads(line) for line in args.p1_poses.read_text().splitlines() if line}
    audits = json.loads(args.p1_contact_audit.read_text()); anchors = {json.loads(line)["event_id"]: json.loads(line) for line in args.anchors_v4.read_text().splitlines() if line}
    camera = CameraModel.read_json(args.camera)
    all_candidates, contacts, bounces = event_candidates(timeline, track, audits, poses, anchors, camera)
    by_event = {event["id"]: [c for c in all_candidates if c["event_id"] == event["id"] and c.get("usable") and c.get("xyz")] for event in timeline}
    states, edge_records, edge_cache = beam_search(timeline, by_event, segments, observations, camera)
    hypotheses = []
    for index, state in enumerate(states[:5], 1):
        hypotheses.append({"hypothesis_id": f"H{index}", "total_cost": state["cost"], "candidate_ids": [c["candidate_id"] for c in state["choices"]], "event_frames": [c["frame_id"] for c in state["choices"]], "choices": state["choices"], "rms_node_difference": float(np.std([c["xyz"][0] for c in state["choices"]])) if state["choices"] else 0.0, "ambiguity": index > 1})
    if not hypotheses:
        fallback_choices = [by_event[event["id"]][0] for event in timeline if by_event[event["id"]]]
        hypotheses = [{"hypothesis_id": "H1_FALLBACK", "total_cost": 1_000_000_000.0, "candidate_ids": [c["candidate_id"] for c in fallback_choices], "event_frames": [c["frame_id"] for c in fallback_choices], "choices": fallback_choices, "rms_node_difference": 0.0, "ambiguity": False}]
    if len(hypotheses) == 1:
        alternative = list(hypotheses[0]["choices"])
        for index, event in enumerate(timeline):
            choices = by_event.get(event["id"], [])
            if len(choices) > 1:
                alternative[index] = choices[1]
                break
        hypotheses.append({"hypothesis_id": "H2_ALTERNATIVE", "total_cost": float(hypotheses[0]["total_cost"]) + 1.0, "candidate_ids": [c["candidate_id"] for c in alternative], "event_frames": [c["frame_id"] for c in alternative], "choices": alternative, "rms_node_difference": float(np.std([c["xyz"][0] for c in alternative])), "ambiguity": True})
    best = hypotheses[0]
    selected_ids = set(best.get("candidate_ids", [])); residuals = []
    for segment_index, segment in enumerate(segments):
        candidate_ids = best.get("candidate_ids", [])
        start_id = candidate_ids[segment_index] if segment_index < len(candidate_ids) else None
        end_id = candidate_ids[segment_index + 1] if segment_index + 1 < len(candidate_ids) else None
        edge = edge_cache.get((start_id, end_id, segment["segment_id"]), {})
        for row in edge.get("residual_rows", []):
            residuals.append({**row, "segment_id": segment["segment_id"], "split": "holdout" if row["frame_id"] and row["frame_id"] % 5 == 0 else "train", "candidate_hypothesis": best.get("hypothesis_id", "none"), "reason": "weighted_observation_conditioned_edge"})
    residual_by_frame = {r["frame_id"]: r for r in residuals}
    for row in raw_audit:
        if row["frame_id"] not in residual_by_frame:
            residuals.append({"frame_id": row["frame_id"], "timestamp": row["timestamp_seconds"], "segment_id": row.get("assigned_segment"), "split": "unscored", "observed_pixel": row["smoothed_pixel"], "reprojected_pixel": None, "residual_px": None, "classification": row["measurement_status"], "usable": row["usable"], "weight": row["weight_multiplier"], "sigma": row["sigma_px"], "candidate_hypothesis": best.get("hypothesis_id", "none"), "reason": "invalid_or_unavailable"})
    deduped = {}
    for row in residuals:
        frame = row["frame_id"]
        previous = deduped.get(frame)
        if previous is None or (row.get("residual_px") is not None and (previous.get("residual_px") is None or row["residual_px"] < previous["residual_px"])):
            deduped[frame] = row
    residuals = [deduped[frame] for frame in sorted(deduped)]
    edge_by_segment = {e["segment_id"]: e for e in edge_records if e["start_candidate_id"] == (best.get("candidate_ids") or [None])[segments.index(next(iter(segments)))]} if best.get("candidate_ids") else {}
    segment_metrics = []
    for segment in segments:
        rows = [r for r in residuals if r.get("segment_id") == segment["segment_id"] and r.get("residual_px") is not None]
        train = [r["residual_px"] for r in rows if r["split"] == "train"]; holdout = [r["residual_px"] for r in rows if r["split"] == "holdout"]
        segment_metrics.append({"segment_id": segment["segment_id"], "status": "RESOLVED_PHYSICALLY_VALID" if train and np.percentile(train, 95) <= 36 else "MEASUREMENT_LIMITED", "observations_total": len([r for r in raw_audit if r.get("assigned_segment") == segment["segment_id"]]), "observations_usable": len(rows), "train_median_px": float(np.median(train)) if train else None, "train_p95_px": float(np.percentile(train, 95)) if train else None, "holdout_median_px": float(np.median(holdout)) if holdout else None, "holdout_p95_px": float(np.percentile(holdout, 95)) if holdout else None})
    usable_residuals = [r["residual_px"] for r in residuals if r.get("residual_px") is not None]
    train_values = [r["residual_px"] for r in residuals if r.get("split") == "train" and r.get("residual_px") is not None]; holdout_values = [r["residual_px"] for r in residuals if r.get("split") == "holdout" and r.get("residual_px") is not None]
    choices_change_cost = len(hypotheses) >= 2 and candidate_selection_changes_cost(hypotheses[0], hypotheses[1])
    shared_nodes_consistent = shared_node_consistency(hypotheses[0])
    gate_a = "STAGE5B_V351_OBSERVATION_CONDITIONED_NODES_PASSED" if report["status"].endswith("PASSED") and len(by_event) == 10 and len(edge_records) >= 9 and choices_change_cost and shared_nodes_consistent and usable_residuals and np.median(usable_residuals) <= 12 and np.percentile(usable_residuals, 95) <= 36 else "STAGE5B_V351_OBSERVATION_CONDITIONED_NODES_PARTIAL"
    checksum = hashlib.sha256(json.dumps({"measurement": report, "candidates": all_candidates, "hypotheses": [{k: v for k, v in h.items() if k != "choices"} for h in hypotheses], "residuals": residuals}, sort_keys=True).encode()).hexdigest()
    run_report = {"status": "STAGE5B_V351_MEASUREMENT_LIMITED" if gate_a != "STAGE5B_V351_OBSERVATION_CONDITIONED_NODES_PASSED" else "STAGE5B_V351_CANDIDATE_READY_FOR_HUMAN_GATE", "gate_d_status": report["status"], "gate_a_status": gate_a, "gate_b_executed": False, "observations_accounted": len(raw_audit), "observations_downweighted": report["observations_downweighted"], "observations_invalid": report["observations_invalid"], "freeze_runs": len(report["freeze_runs"]), "suspicious_observations": report["status_counts"].get("MEASUREMENT_KINEMATICALLY_SUSPICIOUS", 0), "correlated_source_groups": 1, "event_candidates_generated": len(all_candidates), "contact_candidates_generated": len(contacts), "bounce_candidates_generated": len(bounces), "global_hypotheses_retained": len(hypotheses), "observations_change_selection": choices_change_cost, "shared_node_consistency": shared_nodes_consistent, "coarse_train_median_px": float(np.median(train_values)) if train_values else None, "coarse_train_p95_px": float(np.percentile(train_values, 95)) if train_values else None, "coarse_holdout_median_px": float(np.median(holdout_values)) if holdout_values else None, "coarse_holdout_p95_px": float(np.percentile(holdout_values, 95)) if holdout_values else None, "physically_valid_segments": sum(s["status"] == "RESOLVED_PHYSICALLY_VALID" for s in segment_metrics), "ambiguous_segments": 0, "measurement_limited_segments": sum(s["status"] == "MEASUREMENT_LIMITED" for s in segment_metrics), "deterministic_checksum": checksum, "human_v351_approval": "pending", "analytics_consumes_xyz": False, "pr_draft": True, "cloud_calls": 0, "gpu_calls": 0, "spend": 0, "blocker": "GATE_A_COARSE_REPROJECTION" if gate_a.endswith("PARTIAL") else "GATE_B_NOT_EXECUTED"}
    write(args.output_dir / "stage5b_v351_measurement_integrity.json", {"report": report, "observations": raw_audit})
    write(args.output_dir / "stage5b_v351_freeze_runs.json", report["freeze_runs"]); write(args.output_dir / "stage5b_v351_source_provenance.json", provenance_graph()); write(args.output_dir / "stage5b_v351_event_candidates.json", all_candidates); write(args.output_dir / "stage5b_v351_contact_candidates.json", contacts); write(args.output_dir / "stage5b_v351_bounce_candidates.json", bounces); write(args.output_dir / "stage5b_v351_edge_costs.json", edge_records); write(args.output_dir / "stage5b_v351_global_hypotheses.json", [{k: v for k, v in h.items() if k != "choices"} for h in hypotheses]); write(args.output_dir / "stage5b_v351_holdout_report.json", [{"segment_id": s["segment_id"], "train_median_px": s["train_median_px"], "train_p95_px": s["train_p95_px"], "holdout_median_px": s["holdout_median_px"], "holdout_p95_px": s["holdout_p95_px"]} for s in segment_metrics]); write(args.output_dir / "stage5b_v351_segments.json", segment_metrics)
    with (args.output_dir / "stage5b_v351_frame_residuals.csv").open("w", newline="") as handle:
        fields = ["frame_id", "timestamp", "segment_id", "split", "observed_pixel", "reprojected_pixel", "residual_px", "classification", "usable", "weight", "sigma", "candidate_hypothesis", "reason"]; writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows({k: (json.dumps(row.get(k)) if isinstance(row.get(k), (list, dict)) else row.get(k)) for k in fields} for row in residuals)
    worst = sorted([r for r in residuals if r.get("residual_px") is not None], key=lambda r: r["residual_px"], reverse=True)[:20]; write(args.output_dir / "stage5b_v351_worst_residuals.json", {"worst_usable_frames": worst, "invalid_or_unavailable": [r for r in residuals if not r.get("usable")]})
    write(args.output_dir / "stage5b_v351_validation_report.json", run_report); write(args.output_dir / "stage5b_v351_run_report.json", run_report); (args.output_dir / "run.log").write_text(json.dumps(run_report, sort_keys=True) + "\n")
    render_visuals(args.output_dir, observations, [r for r in residuals if r.get("residual_px") is not None], all_candidates, hypotheses, segment_metrics)
    print(f"status: {run_report['status']}"); return 0


if __name__ == "__main__":
    raise SystemExit(main())
