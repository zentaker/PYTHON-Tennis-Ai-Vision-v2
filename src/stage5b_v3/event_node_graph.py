"""Shared event-node graph and analytic flight feasibility."""

from __future__ import annotations

from typing import Any

import numpy as np


def build_shared_graph(
    timeline: list[dict[str, Any]],
    contact_candidates: dict[str, list[list[float]]],
    bounce_candidates: dict[str, list[list[float]]],
) -> dict[str, Any]:
    nodes = []
    for event in timeline:
        candidates = (
            contact_candidates[event["event_id"]]
            if event["event_type"] == "contact"
            else bounce_candidates[event["event_id"]]
        )
        nodes.append(
            {
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "frame_id": event["frame_id"],
                "timestamp_seconds": event["timestamp_seconds"],
                "candidates": candidates,
                "selected_candidate_index": 0 if candidates else None,
                "shared_position_xyz": candidates[0] if candidates else None,
                "incoming_edge": f"flight_{int(event['event_id'].split('_')[1]) - 1:02d}"
                if event["previous_event_id"]
                else None,
                "outgoing_edge": f"flight_{int(event['event_id'].split('_')[1]):02d}"
                if event["next_event_id"]
                else None,
            }
        )
    edges = [
        {
            "segment_id": f"flight_{index:02d}",
            "start_event_id": left["event_id"],
            "end_event_id": right["event_id"],
            "start_node_reference": left["event_id"],
            "end_node_reference": right["event_id"],
        }
        for index, (left, right) in enumerate(zip(nodes, nodes[1:], strict=False), 1)
    ]
    return {"nodes": nodes, "edges": edges, "shared_node_consistency": len(nodes)}


def allocate_event_and_interior_observations(
    timeline: list[dict[str, Any]], observations: list[dict[str, Any]]
) -> dict[str, Any]:
    event_frames = {event["frame_id"]: event for event in timeline}
    node_observations = [row | {"event_id": event_frames[row["frame_id"]]["event_id"]} for row in observations if row["frame_id"] in event_frames]
    interiors = [row for row in observations if row["frame_id"] not in event_frames]
    assigned = [row["frame_id"] for row in node_observations + interiors]
    if len(assigned) != len(set(assigned)):
        raise ValueError("duplicated event observation")
    return {
        "event_node_observations": node_observations,
        "interior_observations": interiors,
        "contact_node_observations": sum(event_frames[row["frame_id"]]["event_type"] == "contact" for row in node_observations),
        "bounce_node_observations": sum(event_frames[row["frame_id"]]["event_type"] == "bounce" for row in node_observations),
        "duplicated_observations": 0,
    }


def analytic_ballistic_candidate(
    start_xyz: list[float],
    end_xyz: list[float],
    duration_seconds: float,
    *,
    gravity_mps2: float = 9.81,
    maximum_speed_mps: float = 80.0,
) -> dict[str, Any]:
    if duration_seconds <= 0:
        return {"feasible": False, "reason": "NON_POSITIVE_DURATION"}
    start, end = np.asarray(start_xyz, dtype=float), np.asarray(end_xyz, dtype=float)
    gravity = np.asarray([0.0, 0.0, -gravity_mps2])
    velocity = (end - start - 0.5 * gravity * duration_seconds**2) / duration_seconds
    times = np.linspace(0, duration_seconds, 80)
    points = start + times[:, None] * velocity + 0.5 * times[:, None] ** 2 * gravity
    speed = float(np.linalg.norm(velocity))
    negative = int(np.sum(points[:, 2] < -1e-6))
    crosses_net = (start[1] <= 0 <= end[1]) or (end[1] <= 0 <= start[1])
    if crosses_net and end[1] != start[1]:
        fraction = -start[1] / (end[1] - start[1])
        net_index = int(np.clip(round(fraction * 79), 0, 79))
        net_clearance = float(points[net_index, 2] - 0.914)
    else:
        net_clearance = None
    feasible = negative == 0 and np.isfinite(speed) and speed <= maximum_speed_mps
    if crosses_net:
        feasible = feasible and net_clearance is not None and net_clearance >= 0
    return {
        "feasible": bool(feasible),
        "reason": "FEASIBLE" if feasible else "PHYSICAL_GATE_FAILED",
        "required_initial_velocity": velocity.tolist(),
        "speed_mps": speed,
        "maximum_height_m": float(points[:, 2].max()),
        "net_clearance_m": net_clearance,
        "negative_z_count": negative,
        "sampled_xyz": points.tolist(),
    }
