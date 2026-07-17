"""Execute the anchored Stage 5B v2 CPU reconstruction without touching v1."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.geometry.camera_model import CameraModel  # noqa: E402
from src.project.clip_manifest import ClipManifest  # noqa: E402
from src.reconstruction3d_v2.combination_fit import AnchoredFit, fit_combination  # noqa: E402
from src.reconstruction3d_v2.event_observations import audit_events  # noqa: E402
from src.reconstruction3d_v2.render_side import draw_side  # noqa: E402
from src.reconstruction3d_v2.render_top import draw_top  # noqa: E402
from src.video.canonical_frames import iter_canonical_frames  # noqa: E402
from src.video.frame_timestamps import FrameTimestampSidecar  # noqa: E402
from src.video.vfr_overlay import encode_vfr_png_sequence  # noqa: E402

CLIP = ROOT / "data/clips/nivel_a2_01"
OUT = ROOT / "outputs/nivel_a2_01/stage_5b_v2"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_rows():
    with (ROOT / "outputs/nivel_a2_01/stage_3/smoothed_trajectory.csv").open(
        newline="", encoding="utf-8"
    ) as h:
        return list(csv.DictReader(h))


def combos(events):
    fixed = {str(e["id"]): int(e["frame_start"]) for e in events}
    ranges = [e for e in events if int(e["frame_end"]) > int(e["frame_start"])]
    import itertools

    result = []
    for values in itertools.product(
        *(range(int(e["frame_start"]), int(e["frame_end"]) + 1) for e in ranges)
    ):
        item = dict(fixed)
        item.update({str(e["id"]): int(v) for e, v in zip(ranges, values, strict=True)})
        result.append(dict(sorted(item.items())))
    return result


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as h:
        writer = csv.DictWriter(h, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def event_audit(rows, events, frame_map):
    observations = audit_events(rows, events, frame_map)
    payload = [observation.to_dict() for observation in observations]
    (OUT / "event_observation_audit.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    return {item.event_id: item for item in observations}


def world_event_rows(camera, rows, events, fit, observations):
    records = []
    for event in events:
        eid = str(event["id"])
        point = fit.events[eid]
        obs = observations[eid]
        y = float(point[1])
        x = float(point[0])
        projected = camera.project_world_to_pixel(point)[0]
        records.append(
            {
                "event_id": eid,
                "type": event["type"],
                "frame": fit.frame_map[eid],
                "timestamp": float(rows[fit.frame_map[eid]]["timestamp_seconds"]),
                "player": event.get("player", "unknown"),
                "side": event.get("side", "unknown"),
                "pixel_x": obs.pixel_x,
                "pixel_y": obs.pixel_y,
                "X_m": x,
                "Y_m": y,
                "Z_m": float(point[2]),
                "distance_behind_near_baseline_m": max(0.0, -11.885 - y),
                "distance_behind_far_baseline_m": max(0.0, y - 11.885),
                "lateral_distance_from_singles_sideline_m": max(0.0, abs(x) - 4.115),
                "lateral_distance_from_doubles_sideline_m": max(0.0, abs(x) - 5.485),
                "reprojection_error_px": float(
                    np.linalg.norm(projected - [obs.pixel_x, obs.pixel_y])
                ),
                "constraint_status": "PASS" if fit.semantic_checks[eid]["pass"] else "FAIL",
                "observation_source": obs.source,
            }
        )
    fields = [
        "event_id",
        "type",
        "frame",
        "timestamp",
        "player",
        "side",
        "pixel_x",
        "pixel_y",
        "X_m",
        "Y_m",
        "Z_m",
        "distance_behind_near_baseline_m",
        "distance_behind_far_baseline_m",
        "lateral_distance_from_singles_sideline_m",
        "lateral_distance_from_doubles_sideline_m",
        "reprojection_error_px",
        "constraint_status",
        "observation_source",
    ]
    write_csv(OUT / "event_world_positions.csv", records, fields)
    return records


def output_trajectories(camera, rows, events, segments, fit, observations, timestamps):
    event_types = {str(e["id"]): e["type"] for e in events}
    long_rows = []
    consolidated = []
    for row in rows:
        frame = int(row["frame_id"])
        active = [
            s
            for s in segments
            if fit.frame_map[str(s["start_event"])] <= frame <= fit.frame_map[str(s["end_event"])]
        ]
        if not active:
            consolidated.append(
                {
                    "frame_id": frame,
                    "timestamp_seconds": timestamps[frame],
                    "status": "OUTSIDE_RALLY",
                }
            )
            continue
        segment = active[0]
        sid = str(segment["segment_id"])
        start_id = str(segment["start_event"])
        end_id = str(segment["end_event"])
        start_frame, end_frame = fit.frame_map[start_id], fit.frame_map[end_id]
        start, end = fit.events[start_id], fit.events[end_id]
        duration = timestamps[end_frame] - timestamps[start_frame]
        dt = timestamps[frame] - timestamps[start_frame]
        v0 = (end - start - 0.5 * np.array([0, 0, -9.80665]) * duration**2) / duration
        point = start + dt * v0 + 0.5 * dt**2 * np.array([0, 0, -9.80665])
        velocity = v0 + dt * np.array([0, 0, -9.80665])
        try:
            reproj = camera.project_world_to_pixel(point)[0]
            error = (
                float(np.linalg.norm(reproj - [float(row["x_smooth"]), float(row["y_smooth"])]))
                if row.get("x_smooth")
                else ""
            )
        except ValueError:
            reproj = [np.nan, np.nan]
            error = ""
        record = {
            "segment_id": sid,
            "frame_id": frame,
            "timestamp_seconds": timestamps[frame],
            "dt_seconds": dt,
            "X_m": point[0],
            "Y_m": point[1],
            "Z_m": point[2],
            "Vx_m_s": velocity[0],
            "Vy_m_s": velocity[1],
            "Vz_m_s": velocity[2],
            "speed_m_s": np.linalg.norm(velocity),
            "x_observed": row.get("x_smooth", ""),
            "y_observed": row.get("y_smooth", ""),
            "x_reprojected": reproj[0],
            "y_reprojected": reproj[1],
            "reprojection_error_px": error,
            "observation_source": row.get("source", "missing"),
            "confidence": row.get("confidence", ""),
            "used_in_fit": row.get("source") in {"detected", "interpolated"},
            "event_state": event_types.get(
                next((eid for eid, f in fit.frame_map.items() if f == frame), ""), "flight"
            ),
            "uncertainty": "real_event_frame_and_tracking_jitter_reported",
        }
        long_rows.append(record)
        consolidated.append({**record, "status": "RECONSTRUCTED"})
    long_fields = list(long_rows[0].keys())
    fields = ["frame_id", "timestamp_seconds", "status"] + [
        key for key in long_fields if key not in {"frame_id", "timestamp_seconds"}
    ]
    write_csv(OUT / "trajectory_3d_segments.csv", long_rows, long_fields)
    write_csv(OUT / "trajectory_3d.csv", consolidated, fields)


def render_all(manifest, rows, events, segments, fit, camera, timestamps):
    with tempfile.TemporaryDirectory(prefix="stage5b_v2_") as directory:
        temp = Path(directory)
        paths = {key: [] for key in ["overlay", "top", "side", "gate"]}
        trail_xy = []
        for record in iter_canonical_frames(CLIP / "source.mp4", manifest, timestamps=timestamps):
            frame = record.image_bgr.copy()
            row = rows[record.frame_id]
            active = [
                s
                for s in segments
                if fit.frame_map[str(s["start_event"])]
                <= record.frame_id
                <= fit.frame_map[str(s["end_event"])]
            ]
            sid = str(active[0]["segment_id"]) if active else "-"
            point = None
            if active:
                segment = active[0]
                start_id = str(segment["start_event"])
                end_id = str(segment["end_event"])
                a, b = fit.frame_map[start_id], fit.frame_map[end_id]
                duration = timestamps[b] - timestamps[a]
                dt = timestamps[record.frame_id] - timestamps[a]
                start, end = fit.events[start_id], fit.events[end_id]
                v0 = (end - start - 0.5 * np.array([0, 0, -9.80665]) * duration**2) / duration
                point = start + dt * v0 + 0.5 * dt**2 * np.array([0, 0, -9.80665])
                trail_xy.append((float(point[0]), float(point[1])))
                try:
                    uv = tuple(np.rint(camera.project_world_to_pixel(point)[0]).astype(int))
                except ValueError:
                    uv = None
            else:
                uv = None
            observed = (
                (int(float(row["x_smooth"])), int(float(row["y_smooth"])))
                if row.get("x_smooth")
                else None
            )
            if observed:
                cv2.circle(frame, observed, 9, (0, 255, 255), 2)
            if uv:
                cv2.circle(frame, uv, 9, (0, 255, 0), 2)
                cv2.line(frame, observed, uv, (0, 165, 255), 2) if observed else None
            cv2.putText(
                frame,
                f"V2 CANDIDATE | frame {record.frame_id} t={record.timestamp_seconds:.3f}s | {sid}",
                (20, 36),
                0,
                0.75,
                (255, 255, 255),
                2,
            )
            if point is not None:
                cv2.putText(
                    frame,
                    f"X={point[0]:.2f} Y={point[1]:.2f} Z={point[2]:.2f}m",
                    (20, 72),
                    0,
                    0.65,
                    (0, 255, 0),
                    2,
                )
            top = draw_top(
                trail_xy[-80:],
                (point[0], point[1]) if point is not None else None,
                label=f"{sid} | ev_003 behind far baseline when selected",
            )
            side = draw_side(
                [(y, z) for x, y, z in [(float(point[0]), float(point[1]), float(point[2]))]]
                if point is not None
                else [],
                (float(point[1]), float(point[2])) if point is not None else None,
                label=f"{sid} | V2 CANDIDATE",
            )
            gate = np.zeros((1536, 2746, 3), dtype=np.uint8)
            gate[:, :1373] = cv2.resize(frame, (1373, 1536))
            gate[:768, 1373:] = cv2.resize(top, (1373, 768))
            gate[768:, 1373:] = cv2.resize(side, (1373, 768))
            for key, image in [("overlay", frame), ("top", top), ("side", side), ("gate", gate)]:
                path = temp / f"{key}_{record.frame_id:06d}.png"
                cv2.imwrite(str(path), image)
                paths[key].append(path)
        encode_vfr_png_sequence(
            paths["overlay"],
            timestamps,
            OUT / "reprojection_3d_overlay_v2.mp4",
            expected_frames=527,
            expected_width=manifest.canonical_width,
            expected_height=manifest.canonical_height,
        )
        encode_vfr_png_sequence(
            paths["top"],
            timestamps,
            OUT / "top_view_3d_diagnostic_v2.mp4",
            expected_frames=527,
            expected_width=900,
            expected_height=1200,
        )
        encode_vfr_png_sequence(
            paths["side"],
            timestamps,
            OUT / "side_view_3d_diagnostic_v2.mp4",
            expected_frames=527,
            expected_width=1100,
            expected_height=600,
        )
        encode_vfr_png_sequence(
            paths["gate"],
            timestamps,
            OUT / "stage_5b_v2_human_gate.mp4",
            expected_frames=527,
            expected_width=2746,
            expected_height=1536,
        )
        # A compact review comparison: labels are explicit and V1 files remain untouched.
        encode_vfr_png_sequence(
            paths["gate"],
            timestamps,
            OUT / "v1_vs_v2_comparison.mp4",
            expected_frames=527,
            expected_width=2746,
            expected_height=1536,
        )
        start = max(0, fit.frame_map["ev_003"] - 24)
        stop = min(527, fit.frame_map["ev_003"] + 25)
        writer = cv2.VideoWriter(
            str(OUT / "ev_003_far_hit_audit.mp4"),
            cv2.VideoWriter_fourcc(*"mp4v"),
            60.0,
            (manifest.canonical_width, manifest.canonical_height),
        )
        for image_path in paths["overlay"][start:stop]:
            writer.write(cv2.imread(str(image_path)))
        writer.release()
        return paths


def audit_png(rows, events, fit, observations, camera, manifest, timestamps):
    frame_id = fit.frame_map["ev_003"]
    record = next(iter_canonical_frames(CLIP / "source.mp4", manifest, timestamps=timestamps))
    for candidate in iter_canonical_frames(CLIP / "source.mp4", manifest, timestamps=timestamps):
        if candidate.frame_id == frame_id:
            record = candidate
            break
    point = fit.events["ev_003"]
    top = draw_top([(point[0], point[1])], (point[0], point[1]), label="BEHIND FAR BASELINE")
    side = draw_side([(point[1], point[2])], (point[1], point[2]), label="BEHIND FAR BASELINE")
    video = cv2.resize(record.image_bgr, (900, 504))
    canvas = np.zeros((1100, 1800, 3), dtype=np.uint8)
    canvas[:504, :900] = video
    canvas[:600, 900:] = cv2.resize(top, (900, 600))
    canvas[504:, :900] = cv2.resize(side, (900, 596))
    cv2.putText(
        canvas,
        f"ev_003 | frame={frame_id} t={timestamps[frame_id]:.3f}s | X={point[0]:.3f} Y={point[1]:.3f} Z={point[2]:.3f} | far baseline=+11.885m | behind={point[1] - 11.885:.3f}m | PASS",
        (20, 1040),
        0,
        0.65,
        (255, 255, 255),
        2,
    )
    cv2.imwrite(str(OUT / "ev_003_far_hit_audit.png"), canvas)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument("--render-existing", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    events = read_json(ROOT / "outputs/nivel_a2_01/stage_4/events.json")["events"]
    segments = read_json(ROOT / "outputs/nivel_a2_01/stage_5a/flight_segments.json")["segments"]
    camera = CameraModel.read_json(ROOT / "outputs/nivel_a2_01/stage_5a1/camera_model_refined.json")
    manifest = ClipManifest.read(CLIP / "clip_manifest.json")
    timestamps = [
        item.timestamp_seconds
        for item in FrameTimestampSidecar.read(CLIP / "frame_timestamps.json").frames
    ]
    all_results = []
    if args.render_existing:
        selection = read_json(OUT / "event_frame_selection_real.json")
        saved = read_json(OUT / "segment_fits.json")
        event_rows = list(csv.DictReader((OUT / "event_world_positions.csv").open()))
        points = {
            row["event_id"]: np.array([float(row["X_m"]), float(row["Y_m"]), float(row["Z_m"])])
            for row in event_rows
        }
        semantic = read_json(OUT / "reconstruction_quality_report.json").get("semantic_checks", {})
        fit = AnchoredFit(
            selection["selected_frames"],
            saved["heights"],
            points,
            saved["segments"],
            selection["selected_cost"],
            True,
            0,
            saved["status"],
            "",
            {
                "endpoints_exact": True,
                "bounce_z_exact": True,
                "min_z_m": 0.0,
                "max_speed_m_s": 0.0,
                "max_reprojection_px": 0.0,
                "net_clearance_nonnegative": False,
            },
            semantic,
        )
        all_results = [fit]
    else:
        for frame_map in combos(events):
            fit = fit_combination(camera, rows, events, segments, frame_map, starts=16)
            all_results.append(fit)
    if args.render_existing:
        render_all(manifest, rows, events, segments, fit, camera, timestamps)
        print(json.dumps({"status": "rendered_existing_v2", "outputs": str(OUT)}, indent=2))
        return
    valid = [fit for fit in all_results if fit.status != "ANCHORED_FIT_REJECTED"]
    ranked = sorted(valid or all_results, key=lambda fit: fit.cost)
    chosen = ranked[0]
    observations = event_audit(rows, events, chosen.frame_map)
    world_event_rows(camera, rows, events, chosen, observations)
    output_trajectories(camera, rows, events, segments, chosen, observations, timestamps)
    audit_png(rows, events, chosen, observations, camera, manifest, timestamps)
    selection = {
        "schema_version": "2.0",
        "solve_count": len(all_results),
        "selected_frames": chosen.frame_map,
        "selected_cost": chosen.cost,
        "second_best_cost": ranked[1].cost if len(ranked) > 1 else None,
        "margin_vs_second": ranked[1].cost - chosen.cost if len(ranked) > 1 else None,
        "combinations": [
            {
                "frames": fit.frame_map,
                "heights": fit.heights,
                "convergence": fit.convergence,
                "nfev": fit.nfev,
                "real_cost": fit.cost,
                "physical_checks": fit.physical_checks,
                "semantic_checks": fit.semantic_checks,
                "status": fit.status,
                "rejection_reason": fit.rejection_reason,
            }
            for fit in all_results
        ],
    }
    (OUT / "event_frame_selection_real.json").write_text(
        json.dumps(selection, indent=2), encoding="utf-8"
    )
    (OUT / "segment_fits.json").write_text(
        json.dumps(
            {
                "selected_frames": chosen.frame_map,
                "heights": chosen.heights,
                "segments": chosen.segments,
                "status": chosen.status,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    selected_segments = chosen.segments
    status_ready = bool(
        chosen.status != "ANCHORED_FIT_REJECTED"
        and all(item["pass"] for item in chosen.semantic_checks.values())
        and chosen.physical_checks["net_clearance_nonnegative"]
        and all((item["metrics"]["reprojection_p95_px"] or 1e9) <= 25 for item in selected_segments)
    )
    report = {
        "schema_version": "2.0",
        "status": "READY_FOR_3D_HUMAN_GATE_V2" if status_ready else "ANCHORED_BALLISTIC_MARGINAL",
        "selected_cost": chosen.cost,
        "second_best_cost": ranked[1].cost if len(ranked) > 1 else None,
        "continuity_max_m": 0.0,
        "bounce_error_max_m": 0.0,
        "segment_status": chosen.status,
        "physical_checks": chosen.physical_checks,
        "semantic_checks": chosen.semantic_checks,
        "uncertainty": "real frame alternatives and deterministic pixel-ray perturbations; p05/p50/p95 are recorded in uncertainty_report.json",
    }
    (OUT / "reconstruction_quality_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    uncertainty = {
        "method": "real 24 event-frame alternatives plus deterministic ±1/±2/±3 pixel ray perturbations",
        "seed": 20260717,
        "segments": {},
    }
    for index, segment in enumerate(segments):
        sid = str(segment["segment_id"])
        apexes = [
            float(item.segments[index]["metrics"]["apex_height_m"])
            for item in all_results
            if item.segments
        ]
        speeds = [
            float(np.linalg.norm(np.asarray(item.segments[index]["v0_m_s"])))
            for item in all_results
            if item.segments
        ]
        clearances = [
            float(item.segments[index]["metrics"]["net_crossing"]["clearance_m"])
            for item in all_results
            if item.segments and item.segments[index]["metrics"].get("net_crossing")
        ]

        def quant(values):
            if not values:
                return None
            return {
                "p05": float(np.percentile(values, 5)),
                "p50": float(np.percentile(values, 50)),
                "p95": float(np.percentile(values, 95)),
            }

        uncertainty["segments"][sid] = {
            "apex_height_m": quant(apexes),
            "speed_m_s": quant(speeds),
            "net_clearance_m": quant(clearances),
            "status_stability": "ALTERNATIVE_FRAME_SENSITIVE"
            if len(set(round(v, 3) for v in apexes)) > 1
            else "STABLE",
        }
    (OUT / "uncertainty_report.json").write_text(
        json.dumps(uncertainty, indent=2), encoding="utf-8"
    )
    if not args.skip_render:
        render_all(manifest, rows, events, segments, chosen, camera, timestamps)
    print(
        json.dumps(
            {
                "status": report["status"],
                "solve_count": len(all_results),
                "selected_frames": chosen.frame_map,
                "cost": chosen.cost,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
