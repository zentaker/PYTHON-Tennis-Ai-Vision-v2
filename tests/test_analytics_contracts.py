import json

import pytest

from src.analytics.contracts import (
    AnalyticsEventInput,
    ClassifiedStroke,
    ConfidenceValue,
    StrokeAnalyticsRecord,
)


def test_confidence_range_and_serialization():
    with pytest.raises(ValueError):
        ConfidenceValue("test", "test", 1.01)
    record = StrokeAnalyticsRecord("1.0", AnalyticsEventInput("e1", 1.25), ClassifiedStroke())
    assert json.loads(json.dumps(record.to_dict()))["stroke"]["stroke_side"] == "unknown"
