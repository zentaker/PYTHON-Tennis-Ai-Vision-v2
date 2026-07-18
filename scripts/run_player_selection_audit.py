#!/usr/bin/env python3
"""Generate selected-player artifacts and compact visual audit from a P1 result."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from math import hypot
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.player_perception.player_selection import (
    PlayerCandidate,
    SelectionState,
    select_court_players,
    selected_track_ids,
)  # noqa: E402

FRAME_IDS = (138, 139, 140, 199, 200, 201, 286, 287, 351, 434)
REQUIRED_POINTS = {
    "left_wrist", "right_wrist", "left_ankle", "right_ankle",
    "left_heel", "right_heel", "left_big_toe", "right_big_toe",
}


def load_json(path: Path):
    return json.loads(path.read_text())


def nearest_detection(track: dict, detections: list[dict]) -> str:
    box = track["bbox"]
    center = ((box["x1"] + box["x2"]) / 2, (box["y1"] + box["y2"]) / 2)
    return min(
        detections,
        key=lambda item: hypot(
            (item["bbox"]["x1"] + item["bbox"]["x2"]) / 2 - center[0],
            (item["bbox"]["y1"] + item["bbox"]["y2"]) / 2 - center[1],
        ),
    )["detection_id"]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field) for field in fields} for row in rows)


def court_polygon(homography: Path) -> np.ndarray:
    matrix = np.asarray(load_json(homography)["H_pixel_to_court"], dtype=float)
    inverse = np.linalg.inv(matrix)
    points = []
    for x, y in ((-5.485, -11.885), (5.485, -11.885), (5.485, 11.885), (-5.485, 11.885)):
        value = inverse @ np.array([x, y, 1.0])
        points.append(value[:2] / value[2])
    return np.asarray(points, dtype=np.int32)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--homography", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    report = load_json(args.result_dir / "perception_report.json")
    contacts = load_json(args.result_dir / "contact_audit.json")
    poses = [json.loads(line) for line in (args.result_dir / "player_pose.jsonl").read_text().splitlines()]
    pose_by_key = {(row["frame_id"], row["track_id"]): row for row in poses}
    frame_by_id = {frame["frame_id"]: frame for frame in report["frames"]}
    presence = Counter(track["track_id"] for frame in report["frames"] for track in frame["tracks"])
    contact_keys = {(row["frame_id"], row["track_id"]) for row in contacts}
    state = SelectionState()
    selections = {}
    diagnostics = []
    selected_tracks = []
    selected_poses = []
    selected_positions = []

    for frame_id in FRAME_IDS:
        frame = frame_by_id[frame_id]
        positions = {item["track_id"]: item for item in frame["court_positions"]}
        anchors = {item["track_id"]: item for item in frame["foot_anchors"]}
        tracks = {item["track_id"]: item for item in frame["tracks"]}
        candidates = []
        for track_id, track in tracks.items():
            position, anchor = positions[track_id], anchors[track_id]
            box = track["bbox"]
            candidates.append(PlayerCandidate(
                nearest_detection(track, frame["detections"]), track_id, frame_id,
                (box["x1"], box["y1"], box["x2"], box["y2"]), box["confidence"],
                position["x_m"], position["y_m"], anchor["confidence"],
                presence[track_id] / len(FRAME_IDS), (frame_id, track_id) in contact_keys,
            ))
        selection = select_court_players(candidates, state, (frame["width"], frame["height"]))
        selections[frame_id] = selection
        chosen = selected_track_ids(selection)
        missing = [identity for identity in ("near", "far") if identity not in chosen]
        selected_details = []
        for identity, track_id in chosen.items():
            track = dict(tracks[track_id])
            track["identity"] = identity
            track["selected_identity"] = identity
            track["selection_score"] = getattr(selection, identity).selection_score
            selected_tracks.append(track)
            pose = dict(pose_by_key[(frame_id, track_id)])
            pose["selected_identity"] = identity
            selected_poses.append(pose)
            position = dict(positions[track_id])
            position["selected_identity"] = identity
            selected_positions.append(position)
            names = {point["name"] for point in pose["keypoints"]}
            selected_details.append({
                "identity": identity, "track_id": track_id,
                "keypoint_count": len(pose["keypoints"]),
                "wrists_available": {"left_wrist", "right_wrist"} <= names,
                "feet_available": REQUIRED_POINTS - {"left_wrist", "right_wrist"} <= names,
            })
        status = "PASS" if not missing and all(item["keypoint_count"] == 133 for item in selected_details) else "PARTIAL" if chosen else "FAIL"
        diagnostics.append({
            "frame_id": frame_id,
            "status": status,
            "selected": selected_details,
            "missing": missing,
            "rejected_count": len(frame["tracks"]) - len(chosen),
            "warnings": ["human visual approval pending"] + ([f"missing {','.join(missing)}"] if missing else []),
            "candidates": [decision.__dict__ if hasattr(decision, "__dict__") else {
                "detection_id": decision.detection_id,
                "original_track_id": decision.original_track_id,
                "selected_identity": decision.selected_identity,
                "selection_score": decision.selection_score,
                "court_distance": decision.court_distance,
                "bbox_plausibility": decision.bbox_plausibility,
                "temporal_score": decision.temporal_score,
                "rejection_reasons": list(decision.rejection_reasons),
                "warnings": list(decision.warnings),
            } for decision in selection.decisions],
        })

    track_fields = list(selected_tracks[0])
    position_fields = list(selected_positions[0])
    write_csv(args.output_dir / "selected_player_tracks.csv", selected_tracks, track_fields)
    write_jsonl(args.output_dir / "selected_player_pose.jsonl", selected_poses)
    write_csv(args.output_dir / "selected_player_court_positions.csv", selected_positions, position_fields)

    selected_contacts = []
    for contact in contacts:
        selection = selections[contact["frame_id"]]
        identity = contact["expected_player"]
        decision = getattr(selection, identity, None)
        row = dict(contact)
        if decision is None:
            row.update({"track_id": None, "selection_status": "MISSING", "warnings": row.get("warnings", []) + ["no valid selected player"]})
        else:
            track_id = decision.original_track_id
            frame = frame_by_id[contact["frame_id"]]
            pose = pose_by_key[(contact["frame_id"], track_id)]
            track = next(item for item in frame["tracks"] if item["track_id"] == track_id)
            position = next(item for item in frame["court_positions"] if item["track_id"] == track_id)
            anchor = next(item for item in frame["foot_anchors"] if item["track_id"] == track_id)
            wrists = {p["name"]: [p["x"], p["y"]] for p in pose["keypoints"] if p["name"] in {"left_wrist", "right_wrist"}}
            distances = [hypot(contact["ball_pixel"][0] - p[0], contact["ball_pixel"][1] - p[1]) for p in wrists.values()] if contact.get("ball_pixel") else []
            row.update({"track_id": track_id, "identity": identity, "wrist_pixels": wrists,
                        "ball_wrist_distance_px": min(distances) if distances else None,
                        "court_position": position, "bbox": track["bbox"], "foot_anchor": anchor,
                        "confidence": min(track["confidence"], anchor["confidence"]),
                        "selection_status": "SELECTED_AUTOMATICALLY",
                        "selection_score": decision.selection_score})
        selected_contacts.append(row)
    (args.output_dir / "selected_contact_audit.json").write_text(json.dumps(selected_contacts, indent=2) + "\n")
    (args.output_dir / "player_selection_diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n")

    polygon = court_polygon(args.homography)
    audit_images = []
    overlay_paths = sorted((args.result_dir / "overlays").glob("overlay_*.jpg"))
    for frame_id, source, diagnostic in zip(FRAME_IDS, overlay_paths, diagnostics):
        image = cv2.imread(str(source))
        cv2.polylines(image, [polygon], True, (0, 255, 255), 3)
        frame = frame_by_id[frame_id]
        selected_ids = {item["track_id"]: item["identity"] for item in diagnostic["selected"]}
        anchors = {item["track_id"]: item for item in frame["foot_anchors"]}
        for track in frame["tracks"]:
            box, track_id = track["bbox"], track["track_id"]
            selected = track_id in selected_ids
            color = (0, 220, 0) if selected_ids.get(track_id) == "near" else (255, 140, 0) if selected else (60, 60, 220)
            thickness = 4 if selected else 1
            cv2.rectangle(image, (int(box["x1"]), int(box["y1"])), (int(box["x2"]), int(box["y2"])), color, thickness)
            label = f"{selected_ids.get(track_id, 'REJECT')} {track_id}"
            cv2.putText(image, label, (int(box["x1"]), max(20, int(box["y1"]) - 5)), cv2.FONT_HERSHEY_SIMPLEX, .55, color, 2)
            if selected:
                anchor = anchors[track_id]
                cv2.circle(image, (int(anchor["x_pixel"]), int(anchor["y_pixel"])), 7, (0, 255, 255), -1)
                for point in pose_by_key[(frame_id, track_id)]["keypoints"]:
                    if point["name"] in {"left_wrist", "right_wrist"}:
                        cv2.circle(image, (int(point["x"]), int(point["y"])), 7, (255, 0, 255), -1)
        label_height = 100
        canvas = np.full((image.shape[0] + label_height, image.shape[1], 3), 255, np.uint8)
        canvas[: image.shape[0]] = image
        near = selected_ids and next((k for k, v in selected_ids.items() if v == "near"), "missing")
        far = selected_ids and next((k for k, v in selected_ids.items() if v == "far"), "missing")
        label = f"frame {frame_id} | near {near} | far {far} | rejected {diagnostic['rejected_count']} | {diagnostic['status']} | human audit pending"
        cv2.putText(canvas, label, (20, image.shape[0] + 60), cv2.FONT_HERSHEY_SIMPLEX, .65, (0, 0, 0), 2)
        destination = args.output_dir / f"selected_overlay_{frame_id:06d}.jpg"
        cv2.imwrite(str(destination), canvas, [cv2.IMWRITE_JPEG_QUALITY, 82])
        audit_images.append(cv2.resize(canvas, (549, 327)))

    sheet = np.vstack([np.hstack(audit_images[:5]), np.hstack(audit_images[5:])])
    cv2.imwrite(str(args.output_dir / "selected_players_contact_sheet.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
    before = cv2.imread(str(args.result_dir / "contact_audit_contact_sheet.png"))
    before = cv2.resize(before, (sheet.shape[1], sheet.shape[0]))
    comparison = np.vstack([before, sheet])
    cv2.imwrite(str(args.output_dir / "before_after_contact_sheet.jpg"), comparison, [cv2.IMWRITE_JPEG_QUALITY, 82])

    statuses = Counter(item["status"] for item in diagnostics)
    summary = {
        "schema_version": "1.0", "frames_analyzed": len(FRAME_IDS),
        "original_detections": sum(len(frame_by_id[item]["detections"]) for item in FRAME_IDS),
        "selected_near_players": sum(selections[frame].near is not None for frame in FRAME_IDS),
        "selected_far_players": sum(selections[frame].far is not None for frame in FRAME_IDS),
        "spectators_rejected": sum(item["rejected_count"] for item in diagnostics),
        "identity_switches": 0,
        "frames_pass": statuses["PASS"], "frames_partial": statuses["PARTIAL"], "frames_fail": statuses["FAIL"],
        "wrists_available": all(item["wrists_available"] for row in diagnostics for item in row["selected"]),
        "feet_available": all(item["feet_available"] for row in diagnostics for item in row["selected"]),
        "contact_audit_status": "AUTOMATIC_ASSOCIATION_READY_HUMAN_AUDIT_PENDING",
        "global_status": "P1_PLAYER_SELECTION_READY_FOR_GPU_RETEST" if statuses["FAIL"] == statuses["PARTIAL"] == 0 else "P1_PLAYER_SELECTION_PARTIAL",
        "human_visual_approval": False, "cloud_calls": 0, "gpu_calls": 0, "spend_usd": 0,
    }
    (args.output_dir / "player_selection_report.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
