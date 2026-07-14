"""Normalized event schema for Stage 4 Level A."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


DEFAULT_FPS = 60.0

ALLOWED_EVENT_TYPES = frozenset({"serve", "hit", "bounce", "unknown"})
ALLOWED_PLAYERS = frozenset({"near", "far", "unknown"})
ALLOWED_SIDES = frozenset({"near", "far", "unknown"})
ALLOWED_SHOT_TYPES = frozenset(
    {
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
)
ALLOWED_COURT_ZONES = frozenset(
    {
        "zona_saque_derecha",
        "zona_saque_izquierda",
        "fondo",
        "media",
        "aprox_red",
        "red",
        "unknown",
    }
)
MANUAL_SOURCE = "manual_annotation"
RAW_EVENT_FIELDS = frozenset(
    {
        "id",
        "type",
        "frame_range",
        "player",
        "side",
        "shot_type",
        "court_zone",
        "source",
        "notes",
    }
)


class EventValidationError(ValueError):
    """Raised when an annotation cannot be represented without guessing."""


def validate_fps(value: Any) -> float:
    """Return a positive FPS value or raise a clear validation error."""
    if isinstance(value, bool):
        raise EventValidationError("fps must be a positive number")
    try:
        fps = float(value)
    except (TypeError, ValueError) as exc:
        raise EventValidationError("fps must be a positive number") from exc
    if fps <= 0:
        raise EventValidationError("fps must be greater than zero")
    return fps


def _required_text(raw: Mapping[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise EventValidationError(f"{key} must be a non-empty string")
    return value.strip()


def _enum_value(
    raw: Mapping[str, Any],
    key: str,
    allowed: frozenset[str],
    *,
    default: str = "unknown",
) -> str:
    value = raw.get(key, default)
    if not isinstance(value, str) or value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise EventValidationError(f"{key} must be one of: {choices}")
    return value


def _frame_value(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EventValidationError(f"{label} must be a non-negative integer")
    if value < 0:
        raise EventValidationError(f"{label} must be a non-negative integer")
    return value


def parse_frame_range(value: Any) -> tuple[int, int]:
    """Validate and unpack the inclusive two-element frame range."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise EventValidationError("frame_range must contain exactly [start, end]")
    start = _frame_value(value[0], "frame_range start")
    end = _frame_value(value[1], "frame_range end")
    if start > end:
        raise EventValidationError("frame_range start must be <= end")
    return start, end


@dataclass(frozen=True)
class NormalizedEvent:
    """Lossless normalized representation of one manually supplied event."""

    id: str
    type: str
    frame_start: int
    frame_end: int
    frame_mid: float
    time_start_seconds: float
    time_end_seconds: float
    time_mid_seconds: float
    player: str
    side: str
    shot_type: str
    court_zone: str
    source: str
    notes: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary in schema field order."""
        return asdict(self)


def normalize_narrative_event(raw: Any, fps: float = DEFAULT_FPS) -> NormalizedEvent:
    """Convert one manual narrative event without creating missing events."""
    if not isinstance(raw, Mapping):
        raise EventValidationError("event must be a JSON object")

    unexpected_fields = sorted(set(raw).difference(RAW_EVENT_FIELDS))
    if unexpected_fields:
        joined = ", ".join(unexpected_fields)
        raise EventValidationError(
            f"unsupported event fields would be lost during normalization: {joined}"
        )

    validated_fps = validate_fps(fps)
    event_id = _required_text(raw, "id")
    event_type = _enum_value(raw, "type", ALLOWED_EVENT_TYPES)
    frame_start, frame_end = parse_frame_range(raw.get("frame_range"))
    player = _enum_value(raw, "player", ALLOWED_PLAYERS)
    side = _enum_value(raw, "side", ALLOWED_SIDES)
    shot_type = _enum_value(raw, "shot_type", ALLOWED_SHOT_TYPES)
    court_zone = _enum_value(raw, "court_zone", ALLOWED_COURT_ZONES)

    notes = raw.get("notes", "")
    if not isinstance(notes, str):
        raise EventValidationError("notes must be a string")

    source = raw.get("source", MANUAL_SOURCE)
    if source != MANUAL_SOURCE:
        raise EventValidationError(f"source must be {MANUAL_SOURCE}")

    frame_mid = (frame_start + frame_end) / 2.0
    return NormalizedEvent(
        id=event_id,
        type=event_type,
        frame_start=frame_start,
        frame_end=frame_end,
        frame_mid=frame_mid,
        time_start_seconds=frame_start / validated_fps,
        time_end_seconds=frame_end / validated_fps,
        time_mid_seconds=frame_mid / validated_fps,
        player=player,
        side=side,
        shot_type=shot_type,
        court_zone=court_zone,
        source=MANUAL_SOURCE,
        notes=notes,
    )
