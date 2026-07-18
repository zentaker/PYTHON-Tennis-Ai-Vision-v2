"""Deterministic court-player selection applied after person perception."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot
from typing import Iterable, Mapping

COURT_HALF_WIDTH_M = 5.485
COURT_HALF_LENGTH_M = 11.885


@dataclass(frozen=True, slots=True)
class PlayerCandidate:
    detection_id: str
    track_id: str
    frame_id: int
    bbox: tuple[float, float, float, float]
    detector_confidence: float
    court_x_m: float
    court_y_m: float
    foot_confidence: float
    temporal_presence: float = 0.0
    contact_compatible: bool = False


@dataclass(frozen=True, slots=True)
class CandidateDecision:
    detection_id: str
    original_track_id: str
    selected_identity: str | None
    selection_score: float
    court_distance: float
    bbox_plausibility: float
    temporal_score: float
    rejection_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(slots=True)
class SelectionState:
    track_by_identity: dict[str, str] = field(default_factory=dict)
    center_by_identity: dict[str, tuple[float, float]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FrameSelection:
    frame_id: int
    near: CandidateDecision | None
    far: CandidateDecision | None
    decisions: tuple[CandidateDecision, ...]


def court_distance(x_m: float, y_m: float) -> float:
    """Euclidean distance to the regulation doubles-court rectangle."""
    dx = max(0.0, abs(x_m) - COURT_HALF_WIDTH_M)
    dy = max(0.0, abs(y_m) - COURT_HALF_LENGTH_M)
    return hypot(dx, dy)


def _bbox_plausibility(candidate: PlayerCandidate, image_size: tuple[int, int]) -> float:
    width, height = image_size
    x1, y1, x2, y2 = candidate.bbox
    box_width = max(0.0, x2 - x1) / width
    box_height = max(0.0, y2 - y1) / height
    if box_width < 0.01 or box_height < 0.04 or box_width > 0.25 or box_height > 0.65:
        return 0.0
    expected = 0.25 if candidate.court_y_m < 0 else 0.10
    tolerance = 0.25 if candidate.court_y_m < 0 else 0.12
    return max(0.0, 1.0 - abs(box_height - expected) / tolerance)


def _temporal_score(
    candidate: PlayerCandidate, identity: str, state: SelectionState, image_size: tuple[int, int]
) -> float:
    if state.track_by_identity.get(identity) == candidate.track_id:
        return 1.0
    previous = state.center_by_identity.get(identity)
    if previous is None:
        return candidate.temporal_presence
    x1, y1, x2, y2 = candidate.bbox
    center = ((x1 + x2) / 2, (y1 + y2) / 2)
    diagonal = hypot(*image_size)
    spatial = max(0.0, 1.0 - hypot(center[0] - previous[0], center[1] - previous[1]) / diagonal)
    return 0.65 * spatial + 0.35 * candidate.temporal_presence


def select_court_players(
    candidates: Iterable[PlayerCandidate],
    state: SelectionState,
    image_size: tuple[int, int],
    *,
    lateral_margin_m: float = 1.5,
    baseline_margin_m: float = 8.5,
    minimum_score: float = 0.35,
) -> FrameSelection:
    """Select at most one valid near and far candidate without spectator fill."""
    candidates = tuple(candidates)
    frame_id = candidates[0].frame_id if candidates else -1
    scored: dict[str, list[tuple[float, PlayerCandidate, CandidateDecision]]] = {
        "near": [],
        "far": [],
    }
    decisions: list[CandidateDecision] = []
    for candidate in candidates:
        identity = "near" if candidate.court_y_m < 0 else "far"
        distance = court_distance(candidate.court_x_m, candidate.court_y_m)
        bbox_score = _bbox_plausibility(candidate, image_size)
        temporal = _temporal_score(candidate, identity, state, image_size)
        reasons: list[str] = []
        if abs(candidate.court_x_m) > COURT_HALF_WIDTH_M + lateral_margin_m:
            reasons.append("outside_lateral_play_area")
        if abs(candidate.court_y_m) > COURT_HALF_LENGTH_M + baseline_margin_m:
            reasons.append("outside_baseline_margin")
        if bbox_score == 0:
            reasons.append("implausible_bbox")
        if candidate.foot_confidence <= 0:
            reasons.append("missing_foot_anchor")
        score = (
            0.35 * max(0.0, 1.0 - distance / baseline_margin_m)
            + 0.20 * bbox_score
            + 0.15 * max(0.0, min(1.0, candidate.detector_confidence))
            + 0.20 * temporal
            + 0.05 * max(0.0, min(1.0, candidate.foot_confidence))
            + 0.05 * float(candidate.contact_compatible)
        )
        if score < minimum_score:
            reasons.append("selection_score_below_threshold")
        decision = CandidateDecision(
            candidate.detection_id,
            candidate.track_id,
            None,
            round(score, 6),
            round(distance, 6),
            round(bbox_score, 6),
            round(temporal, 6),
            tuple(reasons),
        )
        decisions.append(decision)
        if not reasons:
            scored[identity].append((score, candidate, decision))

    selected: dict[str, CandidateDecision | None] = {"near": None, "far": None}
    for identity in ("near", "far"):
        options = sorted(scored[identity], key=lambda item: (-item[0], item[1].track_id))
        if not options:
            continue
        _, candidate, old = options[0]
        chosen = CandidateDecision(
            old.detection_id,
            old.original_track_id,
            identity,
            old.selection_score,
            old.court_distance,
            old.bbox_plausibility,
            old.temporal_score,
            (),
        )
        selected[identity] = chosen
        x1, y1, x2, y2 = candidate.bbox
        state.track_by_identity[identity] = candidate.track_id
        state.center_by_identity[identity] = ((x1 + x2) / 2, (y1 + y2) / 2)
        decisions = [
            chosen
            if item.original_track_id == chosen.original_track_id
            else CandidateDecision(
                item.detection_id,
                item.original_track_id,
                None,
                item.selection_score,
                item.court_distance,
                item.bbox_plausibility,
                item.temporal_score,
                item.rejection_reasons or ("lower_ranked_same_side",),
                item.warnings,
            )
            if item.original_track_id in {option[1].track_id for option in options[1:]}
            else item
            for item in decisions
        ]
    return FrameSelection(frame_id, selected["near"], selected["far"], tuple(decisions))


def selected_track_ids(selection: FrameSelection) -> Mapping[str, str]:
    return {
        identity: decision.original_track_id
        for identity, decision in (("near", selection.near), ("far", selection.far))
        if decision is not None
    }
