import json

import pytest

from src.analytics.adapters.stage4_events import adapt_stage4_event


@pytest.mark.parametrize(
    ("label", "field", "expected"),
    [
        ("saque", "stroke_side", "serve"),
        ("derecha", "stroke_side", "forehand"),
        ("revés", "stroke_side", "backhand"),
        ("volea", "contact_mode", "volley"),
        ("slice", "spin_family", "slice"),
        ("dejada", "tactical_shape", "drop"),
        ("globo", "tactical_shape", "lob"),
    ],
)
def test_conservative_mapping(label, field, expected):
    result = adapt_stage4_event(json.dumps({"shot_type": label}))
    assert getattr(result, field) == expected


def test_slice_does_not_invent_side_and_unknown_stays_unknown():
    result = adapt_stage4_event({"shot_type": "slice"})
    assert result.stroke_side == "unknown"
    assert result.contact_mode == "unknown"
    unknown = adapt_stage4_event({"shot_type": "unknown"})
    assert {unknown.stroke_side, unknown.contact_mode, unknown.spin_family,
            unknown.tactical_shape} == {"unknown"}
