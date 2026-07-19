"""Player-aware contact hypotheses derived from accepted serialized P1 evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import exp
from typing import Any

import numpy as np

from src.geometry.camera_model import CameraModel

from .camera import point_on_pixel_ray_at_height
from .p1_inputs import P1ContactInput


@dataclass(frozen=True, slots=True)
class ContactAnchor:
    event_id: str
    frame_id: int
    timestamp_seconds: float
    track_id: str
    player_identity: str
    player_x_m: float
    player_y_m: float
    x_m: float
    y_m: float
    z_m: float
    wrist_used: str
    wrist_pixels: dict[str, list[float]]
    ball_pixel: tuple[float, float]
    wrist_reprojection_error_px: float
    ball_ray_constraint_residual_px: float
    wrist_xyz_m: tuple[float, float, float]
    racket_distance_m: float
    player_contact_distance_m: float
    contact_confidence: float
    uncertainty_m: tuple[float, float, float]
    hypothesis_id: str
    ambiguity_status: str
    constraint_sources: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def contact_hypotheses(
    contact: P1ContactInput,
    camera: CameraModel,
    config: dict[str, Any],
    max_hypotheses: int,
) -> tuple[ContactAnchor, ...]:
    ball = tuple(float(value) for value in contact.audit["ball_pixel"])
    wrists = contact.audit["wrist_pixels"]
    player_xy = np.array([contact.player_x_m, contact.player_y_m], dtype=float)
    candidates: list[tuple[float, ContactAnchor]] = []
    for index, height in enumerate(config["contact_height_hypotheses_m"]):
        point = point_on_pixel_ray_at_height(camera, ball, float(height))
        horizontal = float(np.linalg.norm(point[:2] - player_xy))
        wrist_candidates = []
        for wrist_name in ("left_wrist", "right_wrist"):
            for wrist_height in config.get("wrist_height_hypotheses_m", [0.8, 1.2, 1.6, 2.0, 2.4]):
                wrist_xyz = point_on_pixel_ray_at_height(
                    camera, tuple(float(value) for value in wrists[wrist_name]), float(wrist_height)
                )
                body_distance = float(np.linalg.norm(wrist_xyz[:2] - player_xy))
                racket_distance = float(np.linalg.norm(point - wrist_xyz))
                wrist_candidates.append(
                    (
                        body_distance / float(config["max_horizontal_reach_m"])
                        + abs(racket_distance - float(config["racket_extension_m"]))
                        / float(config["racket_extension_m"]),
                        wrist_name,
                        wrist_xyz,
                        racket_distance,
                    )
                )
        _, wrist_name, wrist_xyz, racket_distance = min(wrist_candidates, key=lambda item: item[0])
        wrist_error = float(
            np.linalg.norm(camera.project_world_to_pixel([wrist_xyz])[0] - wrists[wrist_name])
        )
        effective_reach = float(config["max_horizontal_reach_m"]) + float(
            config["racket_extension_m"]
        )
        reach_excess = max(0.0, horizontal - effective_reach)
        score = (
            horizontal / effective_reach
            + reach_excess * float(config["reach_excess_weight"])
            + abs(racket_distance - float(config["racket_extension_m"]))
            / float(config["racket_extension_m"])
        )
        confidence = float(contact.audit["confidence"]) * exp(-0.35 * score)
        warning = () if reach_excess == 0 else ("CONTACT_REACH_EXCEEDS_PLAUSIBLE_LIMIT",)
        anchor = ContactAnchor(
            contact.event_id,
            contact.frame_id,
            contact.timestamp_seconds,
            contact.track_id,
            contact.identity,
            float(contact.player_x_m),
            float(contact.player_y_m),
            float(point[0]),
            float(point[1]),
            float(max(0.0, point[2])),
            wrist_name,
            wrists,
            ball,
            wrist_error,
            float(np.linalg.norm(camera.project_world_to_pixel([point])[0] - ball)),
            tuple(float(value) for value in wrist_xyz),
            racket_distance,
            horizontal,
            max(0.0, min(1.0, confidence)),
            (
                float(config["player_position_uncertainty_m"]),
                float(config["player_position_uncertainty_m"]),
                float(config["contact_height_uncertainty_m"]),
            ),
            f"contact_{contact.event_id}_h{index:02d}",
            "AMBIGUOUS",
            (
                "accepted_p1_player_position",
                "accepted_p1_ball_pixel",
                "accepted_p1_wrist_pixels",
                "camera_pixel_ray",
                "global_anatomical_reach",
                "configurable_racket_extension",
            ),
            warning + ("HITTING_HAND_UNKNOWN_BOTH_WRISTS_EVALUATED",),
        )
        candidates.append((score, anchor))
    return tuple(anchor for _, anchor in sorted(candidates, key=lambda item: (item[0], item[1].hypothesis_id))[:max_hypotheses])
