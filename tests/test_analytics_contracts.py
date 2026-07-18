import json
from dataclasses import asdict, fields

import pytest

from src.analytics.contracts import (
    AnalyticsEventInput,
    BallKinematics,
    ClassifiedStroke,
    ConfidenceValue,
    StrokeAnalyticsRecord,
)


def test_confidence_range_and_serialization():
    with pytest.raises(ValueError):
        ConfidenceValue("test", "test", 1.01)
    record = StrokeAnalyticsRecord("1.0", AnalyticsEventInput("e1", 1.25), ClassifiedStroke())
    serialized = json.loads(json.dumps(record.to_dict()))
    assert serialized["stroke"]["stroke_side"]["value"] == "unknown"
    assert serialized["stroke"]["stroke_side"]["confidence"]["confidence"] == 0.0


def test_ball_kinematics_serialization_is_exact_and_validated():
    result = BallKinematics(
        status="partial",
        method="court_planar_xy",
        speed_unit="metres_per_second",
        outgoing_status="available",
    )
    assert set(asdict(result)) == {field.name for field in fields(BallKinematics)}
    assert result.incoming_status == "unavailable"
    assert result.outgoing_status == "available"
    with pytest.raises(ValueError, match="speed_unit"):
        BallKinematics(status="unavailable", method="pixel_apparent", speed_unit="metres_per_second")
    with pytest.raises(ValueError, match="non-negative"):
        BallKinematics(
            status="available", method="court_planar_xy", speed_unit="metres_per_second",
            outgoing_speed_mps=-1.0,
        )
    with pytest.raises(ValueError, match="must not exceed"):
        BallKinematics(
            status="unavailable", method="court_planar_xy", speed_unit="metres_per_second",
            window_start_seconds=2.0, window_end_seconds=1.0,
        )
