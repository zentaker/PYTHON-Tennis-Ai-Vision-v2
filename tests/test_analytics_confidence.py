import pytest

from src.analytics.confidence import validate_confidence_components
from src.analytics.contracts import ConfidenceValue


def test_components_remain_transparent():
    value = ConfidenceValue("synthetic", "fixture", 0.75, geometry_derived=True)
    assert validate_confidence_components({"speed_confidence": value})["speed_confidence"] == value
    with pytest.raises(ValueError):
        validate_confidence_components({"opaque_total": value})
