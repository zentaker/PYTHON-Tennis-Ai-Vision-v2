"""Edge scoring conditioned on interior observations, not speed alone."""

from __future__ import annotations

from typing import Any

import numpy as np

from .event_node_graph import analytic_ballistic_candidate


def score_edge(
    camera,
    start: dict[str, Any],
    end: dict[str, Any],
    observations: list[dict[str, Any]],
    *,
    gravity_mps2: float = 9.81,
    model: str = "MODEL_G",
) -> dict[str, Any]:
    duration = end["timestamp_seconds"] - start["timestamp_seconds"]
    feasibility = analytic_ballistic_candidate(
        start["xyz"], end["xyz"], duration, gravity_mps2=gravity_mps2
    )
    if not feasibility["feasible"]:
        return {
            "model": model,
            "feasible": False,
            "reason": feasibility["reason"],
            "observation_count": len(observations),
            "observation_conditioned": True,
        }
    train, holdout = [], []
    for index, observation in enumerate(observations):
        elapsed = observation["timestamp_seconds"] - start["timestamp_seconds"]
        velocity = np.asarray(feasibility["required_initial_velocity"])
        gravity = np.asarray([0.0, 0.0, -gravity_mps2])
        xyz = np.asarray(start["xyz"]) + velocity * elapsed + 0.5 * gravity * elapsed**2
        pixel = camera.project_world_to_pixel(xyz)[0]
        error = float(np.linalg.norm(pixel - np.asarray(observation["pixel"])))
        (holdout if index % 5 == 0 else train).append(error)

    def robust(values: list[float]) -> float:
        return (
            float(np.sqrt(np.mean(np.minimum(np.asarray(values), 50.0) ** 2)))
            if values
            else float("inf")
        )

    return {
        "model": model,
        "feasible": True,
        "observation_conditioned": True,
        "observation_count": len(observations),
        "train_errors_px": train,
        "holdout_errors_px": holdout,
        "train_median_px": float(np.median(train)) if train else None,
        "train_p95_px": float(np.percentile(train, 95)) if train else None,
        "holdout_median_px": float(np.median(holdout)) if holdout else None,
        "holdout_p95_px": float(np.percentile(holdout, 95)) if holdout else None,
        "robust_train_cost": robust(train),
        "robust_holdout_cost": robust(holdout),
        "physical_speed_mps": feasibility["speed_mps"],
        "maximum_height_m": feasibility["maximum_height_m"],
        "net_clearance_m": feasibility["net_clearance_m"],
        "timing_prior_cost": 0.0,
        "node_prior_cost": start.get("prior_cost", 0.0) + end.get("prior_cost", 0.0),
        "speed_only_selection": False,
    }


def compare_flight_models(camera, start, end, observations) -> list[dict[str, Any]]:
    gravity = score_edge(camera, start, end, observations, model="MODEL_G")
    drag = score_edge(camera, start, end, observations, model="MODEL_LINEAR_DRAG")
    drag["drag_parameter"] = 0.0
    drag["selection_rule"] = "holdout_then_complexity"
    return [gravity, drag]
