"""Deterministic multi-hypothesis player-aware flight reconstruction."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np

from src.geometry.camera_model import CameraModel
from src.reconstruction3d_v2.ballistic_segments import trajectory_from_endpoints

from .contracts import XYZSample, validate_segment_order
from .p1_inputs import load_p1_contacts
from .player_contact_anchor import contact_hypotheses


def _load_ball(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = []
    for row in rows:
        if (
            row.get("x_smooth")
            and row.get("y_smooth")
            and row.get("is_outlier", "false").lower() != "true"
        ):
            result.append(
                {
                    "frame_id": int(row["frame_id"]),
                    "timestamp_seconds": float(row["timestamp_seconds"]),
                    "pixel": (float(row["x_smooth"]), float(row["y_smooth"])),
                    "confidence": float(row["confidence"]),
                    "source": row["source"],
                }
            )
    return result


def _events(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    events = payload["narrative_events"]
    return sorted(events, key=lambda item: (float(item["time_start_seconds"]), item["id"]))


def _bounce_anchor(camera: CameraModel, observation: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    point = camera.intersect_ray_with_ground(*observation["pixel"])
    return {
        "event_id": event["id"],
        "frame_id": observation["frame_id"],
        "timestamp_seconds": observation["timestamp_seconds"],
        "x_m": float(point[0]),
        "y_m": float(point[1]),
        "z_m": 0.0,
        "player_identity": "unknown",
        "confidence": observation["confidence"],
        "constraint_sources": ["stage4_bounce", "camera_ground_intersection"],
    }


def reconstruct(
    camera_path: Path,
    ball_track_path: Path,
    events_path: Path,
    p1_results_path: Path,
    config_path: Path,
    *,
    seed: int = 42,
    max_hypotheses: int = 3,
) -> dict[str, Any]:
    del seed  # deterministic grid, retained in the public interface and manifest
    camera = CameraModel.read_json(camera_path)
    config = json.loads(config_path.read_text())
    observations = _load_ball(ball_track_path)
    events = _events(events_path)
    by_frame = {row["frame_id"]: row for row in observations}
    contacts = load_p1_contacts(p1_results_path)
    contact_options = {
        item.event_id: contact_hypotheses(item, camera, config, max_hypotheses)
        for item in contacts
    }
    event_observations: dict[str, dict[str, Any]] = {}
    for event in events:
        candidates = list(range(int(event["frame_start"]), int(event["frame_end"]) + 1))
        candidates.extend(
            frame
            for distance in (1, 2)
            for frame in (int(event["frame_start"]) - distance, int(event["frame_end"]) + distance)
        )
        selected = next((by_frame[frame] for frame in candidates if frame in by_frame), None)
        if selected is None:
            raise ValueError(f"{event['id']} has no ball observation within event tolerance")
        event_observations[event["id"]] = selected

    hypotheses: list[dict[str, Any]] = []
    sample_sets: list[list[XYZSample]] = []
    for hypothesis_index in range(max_hypotheses):
        anchors: list[dict[str, Any]] = []
        for event in events:
            observation = event_observations[event["id"]]
            if event["type"] == "bounce":
                anchors.append(_bounce_anchor(camera, observation, event))
            else:
                options = contact_options[event["id"]]
                selected = options[min(hypothesis_index, len(options) - 1)]
                anchors.append(
                    {
                        **selected.to_dict(),
                        "confidence": selected.contact_confidence,
                    }
                )
        samples: list[XYZSample] = []
        errors: list[float] = []
        for segment_index, (start, end) in enumerate(zip(anchors, anchors[1:], strict=False), 1):
            segment_id = f"flight_{segment_index:02d}"
            segment_rows = [
                row
                for row in observations
                if start["timestamp_seconds"] <= row["timestamp_seconds"] <= end["timestamp_seconds"]
            ]
            duration = end["timestamp_seconds"] - start["timestamp_seconds"]
            start_xyz = np.array([start["x_m"], start["y_m"], start["z_m"]])
            end_xyz = np.array([end["x_m"], end["y_m"], end["z_m"]])
            times = np.array([row["timestamp_seconds"] - start["timestamp_seconds"] for row in segment_rows])
            xyz = trajectory_from_endpoints(start_xyz, end_xyz, duration, times)
            xyz[:, 2] = np.maximum(0.0, xyz[:, 2])
            pixels = camera.project_world_to_pixel(xyz)
            for row, point, pixel in zip(segment_rows, xyz, pixels, strict=True):
                error = float(np.linalg.norm(pixel - row["pixel"]))
                errors.append(error)
                event_context = start["event_id"] if row["frame_id"] == start["frame_id"] else "flight"
                identity = start.get("player_identity", "unknown") if event_context != "flight" else "unknown"
                confidence = row["confidence"] * np.exp(-error / float(config["reprojection_confidence_scale_px"]))
                samples.append(
                    XYZSample(
                        row["frame_id"],
                        row["timestamp_seconds"],
                        float(point[0]),
                        float(point[1]),
                        float(point[2]),
                        float(max(0.0, min(1.0, confidence))),
                        "interpolated" if row["source"] == "interpolated" else "observed",
                        segment_id,
                        event_context,
                        error,
                        float(row["pixel"][0]),
                        float(row["pixel"][1]),
                        float(pixel[0]),
                        float(pixel[1]),
                        float(config["camera_uncertainty_m"]),
                        float(config["camera_uncertainty_m"]),
                        float(config["contact_height_uncertainty_m"]),
                        ("ball_pixel", "vfr_timestamp", "ballistic_prior", "event_endpoints"),
                        identity,
                        start["event_id"] if event_context != "flight" and start["event_id"] in contact_options else None,
                        f"global_h{hypothesis_index:02d}",
                        "AMBIGUOUS",
                        ("MONOCULAR_DEPTH_HYPOTHESIS",),
                    )
                )
        validate_segment_order(samples)
        hypotheses.append(
            {
                "hypothesis_id": f"global_h{hypothesis_index:02d}",
                "median_reprojection_error_px": median(errors),
                "p95_reprojection_error_px": float(np.percentile(errors, 95)),
                "anchors": anchors,
            }
        )
        sample_sets.append(samples)

    best_index = min(range(len(hypotheses)), key=lambda index: hypotheses[index]["median_reprojection_error_px"])
    best = sample_sets[best_index]
    alternate_by_frame = [{sample.frame_id: sample for sample in samples} for samples in sample_sets]
    final_samples = []
    for sample in best:
        alternatives = [mapping[sample.frame_id] for mapping in alternate_by_frame if sample.frame_id in mapping]
        spread = np.std([[item.x_m, item.y_m, item.z_m] for item in alternatives], axis=0)
        payload = asdict(sample)
        payload["uncertainty_x_m"] = float(max(spread[0], config["camera_uncertainty_m"]))
        payload["uncertainty_y_m"] = float(max(spread[1], config["camera_uncertainty_m"]))
        payload["uncertainty_z_m"] = float(max(spread[2], config["contact_height_uncertainty_m"]))
        final_samples.append(XYZSample(**payload))
    serialized = [sample.to_dict() for sample in final_samples]
    lines = "".join(json.dumps(row, sort_keys=True) + "\n" for row in serialized)
    return {
        "samples": serialized,
        "xyz_jsonl": lines,
        "checksum": hashlib.sha256(lines.encode()).hexdigest(),
        "contacts": [option[0].to_dict() for option in contact_options.values()],
        "contact_hypotheses": {
            event_id: [candidate.to_dict() for candidate in options]
            for event_id, options in contact_options.items()
        },
        "events": events,
        "hypotheses": hypotheses,
        "segments": [f"flight_{index:02d}" for index in range(1, len(events))],
        "observations_consumed": len({sample.frame_id for sample in final_samples}),
        "best_hypothesis_id": f"global_h{best_index:02d}",
    }
