from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.stage5b_v3.contracts import XYZSample, validate_segment_order


def sample() -> XYZSample:
    return XYZSample(
        1, 0.1, 0.0, 1.0, 0.5, 0.7, "observed", "flight_01", "flight", 2.0,
        100.0, 200.0, 101.0, 201.0,
        0.1, 0.1, 0.2, ("ball_pixel",), "unknown", None, "global_h00", "AMBIGUOUS"
    )


def test_xyz_contract_and_schema() -> None:
    value = sample()
    schema = json.loads(Path("config/stage5b_v3/player_aware_xyz.schema.json").read_text())
    Draft202012Validator(schema).validate(value.to_dict())
    assert value.coordinate_unit == "metres"


def test_negative_z_and_non_increasing_segment_time_are_rejected() -> None:
    with pytest.raises(ValueError, match="z_m"):
        replace(sample(), z_m=-0.1)
    with pytest.raises(ValueError, match="strictly increasing"):
        validate_segment_order([sample(), replace(sample(), frame_id=2)])
