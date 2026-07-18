import pytest
from jsonschema import ValidationError

from src.analytics.contracts import BallKinematics
from src.analytics.schema_validation import (
    load_schemas,
    synthetic_kinematics_states,
    validate_serialized_instances,
    validators,
)


def test_real_serialized_record_and_all_kinematics_states_validate():
    validate_serialized_instances()
    available, partial, unavailable = synthetic_kinematics_states()
    assert (available.status, partial.status, unavailable.status) == (
        "available", "partial", "unavailable"
    )


def test_ball_schema_rejects_additional_field_and_invalid_speed_unit():
    ball_validator, _ = validators()
    payload = synthetic_kinematics_states()[0].to_dict()
    with pytest.raises(ValidationError):
        ball_validator.validate(payload | {"fabricated_metric": 1})
    with pytest.raises(ValidationError):
        ball_validator.validate(payload | {"speed_unit": "mph"})


def test_ball_schema_fields_exactly_match_serialized_dataclass():
    ball_schema, _ = load_schemas()
    serialized = synthetic_kinematics_states()[0].to_dict()
    assert set(ball_schema["properties"]) == set(serialized)
    assert set(ball_schema["required"]) == set(serialized)
    assert set(serialized) == set(BallKinematics.__dataclass_fields__)


def test_record_schema_rejects_extra_evidence_field():
    _, stroke_validator = validators()
    from src.analytics.contracts import (  # local grouping keeps fixture construction explicit
        AnalyticsEventInput,
        ClassifiedStroke,
        EvidenceItem,
        StrokeAnalyticsRecord,
    )

    record = StrokeAnalyticsRecord(
        "1.0",
        AnalyticsEventInput("synthetic", 0.5),
        ClassifiedStroke(),
        synthetic_kinematics_states()[2],
        (EvidenceItem("synthetic", "test", "not real evidence", 1.0),),
    ).to_dict()
    stroke_validator.validate(record)
    record["evidence"][0]["unexpected"] = True
    with pytest.raises(ValidationError):
        stroke_validator.validate(record)
