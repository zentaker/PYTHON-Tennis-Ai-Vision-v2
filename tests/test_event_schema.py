from __future__ import annotations

import pytest

from src.events.event_schema import (
    ALLOWED_COURT_ZONES,
    ALLOWED_EVENT_TYPES,
    ALLOWED_PLAYERS,
    ALLOWED_SHOT_TYPES,
    ALLOWED_SIDES,
    EventValidationError,
    normalize_narrative_event,
)


VALID_EVENT = {
    "id": "ev_001",
    "type": "hit",
    "frame_range": [30, 36],
    "player": "near",
    "side": "near",
    "shot_type": "derecha",
    "court_zone": "fondo",
    "source": "manual_annotation",
    "notes": "Synthetic test event",
}


def test_vocabularies_match_stage_4_contract() -> None:
    assert ALLOWED_EVENT_TYPES == {"serve", "hit", "bounce", "unknown"}
    assert ALLOWED_PLAYERS == {"near", "far", "unknown"}
    assert ALLOWED_SIDES == {"near", "far", "unknown"}
    assert ALLOWED_SHOT_TYPES == {
        "saque",
        "derecha",
        "revés",
        "derecha_invertida",
        "revés_invertido",
        "slice",
        "volea",
        "dejada",
        "globo",
        "unknown",
    }
    assert ALLOWED_COURT_ZONES == {
        "zona_saque_derecha",
        "zona_saque_izquierda",
        "fondo",
        "media",
        "aprox_red",
        "red",
        "unknown",
    }


def test_normalize_event_converts_range_and_seconds() -> None:
    event = normalize_narrative_event(VALID_EVENT, fps=60)

    assert event.frame_start == 30
    assert event.frame_end == 36
    assert event.frame_mid == 33.0
    assert event.time_start_seconds == pytest.approx(0.5)
    assert event.time_end_seconds == pytest.approx(0.6)
    assert event.time_mid_seconds == pytest.approx(0.55)
    assert event.to_dict()["source"] == "manual_annotation"


def test_optional_vocabularies_default_to_unknown() -> None:
    raw = {"id": "ev_001", "type": "unknown", "frame_range": [0, 0]}

    event = normalize_narrative_event(raw)

    assert event.player == "unknown"
    assert event.side == "unknown"
    assert event.shot_type == "unknown"
    assert event.court_zone == "unknown"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("type", "impact"),
        ("player", "center"),
        ("side", "left"),
        ("shot_type", "smash"),
        ("court_zone", "outside"),
    ],
)
def test_invalid_vocabulary_is_rejected(field: str, value: str) -> None:
    raw = dict(VALID_EVENT)
    raw[field] = value

    with pytest.raises(EventValidationError, match=field):
        normalize_narrative_event(raw)


@pytest.mark.parametrize("frame_range", [[4], [5, 4], [-1, 2], [1.5, 2]])
def test_invalid_frame_range_is_rejected(frame_range: list[object]) -> None:
    raw = dict(VALID_EVENT)
    raw["frame_range"] = frame_range

    with pytest.raises(EventValidationError, match="frame_range"):
        normalize_narrative_event(raw)


def test_invalid_source_is_rejected_instead_of_relabelled() -> None:
    raw = dict(VALID_EVENT)
    raw["source"] = "automatic"

    with pytest.raises(EventValidationError, match="source"):
        normalize_narrative_event(raw)


def test_unsupported_fields_are_rejected_instead_of_silently_lost() -> None:
    raw = dict(VALID_EVENT)
    raw["shot_direction"] = "T"

    with pytest.raises(EventValidationError, match="shot_direction"):
        normalize_narrative_event(raw)
