"""Validate Analytics schemas and real serialized contract instances."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .contracts import (
    AnalyticsEventInput,
    BallKinematics,
    ClassifiedStroke,
    EvidenceItem,
    StrokeAnalyticsRecord,
)

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "analytics"


def load_schemas() -> tuple[dict[str, Any], dict[str, Any]]:
    ball = json.loads((CONFIG_DIR / "ball_kinematics.schema.json").read_text())
    stroke = json.loads((CONFIG_DIR / "stroke_analytics.schema.json").read_text())
    return ball, stroke


def validators() -> tuple[Draft202012Validator, Draft202012Validator]:
    ball, stroke = load_schemas()
    Draft202012Validator.check_schema(ball)
    Draft202012Validator.check_schema(stroke)
    registry = Registry().with_resource(ball["$id"], Resource.from_contents(ball))
    return (
        Draft202012Validator(ball, registry=registry),
        Draft202012Validator(stroke, registry=registry),
    )


def synthetic_kinematics_states() -> tuple[BallKinematics, BallKinematics, BallKinematics]:
    common = {"method": "court_planar_xy", "speed_unit": "metres_per_second"}
    available = BallKinematics(
        status="available",
        incoming_status="available",
        outgoing_status="available",
        incoming_speed_mps=10.0,
        incoming_speed_kmh=36.0,
        outgoing_speed_mps=20.0,
        outgoing_speed_kmh=72.0,
        samples_used=10,
        incoming_samples_used=5,
        outgoing_samples_used=5,
        window_start_seconds=0.0,
        window_end_seconds=1.0,
        confidence=1.0,
        incoming_confidence=1.0,
        outgoing_confidence=1.0,
        **common,
    )
    partial = BallKinematics(
        status="partial",
        incoming_status="available",
        incoming_speed_mps=10.0,
        incoming_speed_kmh=36.0,
        samples_used=5,
        incoming_samples_used=5,
        window_start_seconds=0.0,
        window_end_seconds=0.5,
        confidence=1.0,
        incoming_confidence=1.0,
        warnings=("outgoing: insufficient evidence",),
        **common,
    )
    unavailable = BallKinematics(status="unavailable", **common)
    return available, partial, unavailable


def validate_serialized_instances() -> None:
    ball_validator, stroke_validator = validators()
    states = synthetic_kinematics_states()
    for state in states:
        ball_validator.validate(state.to_dict())
    record = StrokeAnalyticsRecord(
        schema_version="1.0",
        event=AnalyticsEventInput("synthetic-contact", 0.5, frame_id=15),
        stroke=ClassifiedStroke(),
        kinematics=states[0],
        evidence=(
            EvidenceItem(
                source="synthetic_fixture",
                method="deterministic_test",
                description="schema validation only; not real tennis evidence",
                confidence=1.0,
                geometry_derived=True,
            ),
        ),
    )
    stroke_validator.validate(record.to_dict())


def main() -> int:
    validate_serialized_instances()
    print("INSTANCE_VALIDATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
