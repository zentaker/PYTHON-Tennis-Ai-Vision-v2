"""Conservative adapter for the historical Stage 4 manual label."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from ..contracts import (
    ClassifiedStroke,
    ConfidenceValue,
    ContactMode,
    SpinFamily,
    StrokeSide,
    TacticalShape,
)

_AMBIGUOUS = {"derecha", "revés", "volea", "slice", "dejada", "globo"}


def adapt_stage4_event(value: Mapping[str, Any] | str) -> ClassifiedStroke:
    """Map only information explicitly present in a Stage 4 manual annotation."""
    payload = json.loads(value) if isinstance(value, str) else dict(value)
    label = str(payload.get("shot_type", "unknown")).strip().lower()
    side, mode = StrokeSide.UNKNOWN, ContactMode.UNKNOWN
    spin, shape = SpinFamily.UNKNOWN, TacticalShape.UNKNOWN
    if label == "saque":
        side, mode = StrokeSide.SERVE, ContactMode.SERVE
    elif label == "derecha":
        side = StrokeSide.FOREHAND
    elif label in {"revés", "reves"}:
        side = StrokeSide.BACKHAND
    elif label == "volea":
        mode = ContactMode.VOLLEY
    elif label == "slice":
        spin = SpinFamily.SLICE
    elif label == "dejada":
        shape = TacticalShape.DROP
    elif label == "globo":
        shape = TacticalShape.LOB

    def evidence(known: bool, dimension: str) -> ConfidenceValue:
        warnings = ()
        if label in _AMBIGUOUS:
            warnings = ("legacy label is ambiguous across analytics dimensions",)
        if not known:
            return ConfidenceValue(
                "stage4_manual_annotation",
                "conservative_legacy_mapping",
                0.0,
                warnings + (f"{dimension} unavailable from legacy label",),
                ("stage4.shot_type",),
                human_labeled=True,
            )
        return ConfidenceValue(
            "stage4_manual_annotation",
            "conservative_legacy_mapping",
            1.0,
            warnings,
            ("stage4.shot_type",),
            human_labeled=True,
        )

    return ClassifiedStroke(
        stroke_side=side,
        contact_mode=mode,
        spin_family=spin,
        tactical_shape=shape,
        stroke_side_confidence=evidence(side != StrokeSide.UNKNOWN, "stroke_side"),
        contact_mode_confidence=evidence(mode != ContactMode.UNKNOWN, "contact_mode"),
        spin_family_confidence=evidence(spin != SpinFamily.UNKNOWN, "spin_family"),
        tactical_shape_confidence=evidence(shape != TacticalShape.UNKNOWN, "tactical_shape"),
    )
