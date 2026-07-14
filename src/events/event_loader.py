"""Load and normalize Stage 4 Level A manual narrative events."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from src.events.event_schema import (
    DEFAULT_FPS,
    EventValidationError,
    NormalizedEvent,
    normalize_narrative_event,
    validate_fps,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ANNOTATION = PROJECT_ROOT / "data" / "reference_clip" / "manual_annotation.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs" / "stage_4" / "events.json"


class MissingNarrativeEventsError(EventValidationError):
    """Raised when the manual gate has no events to normalize."""


def load_annotation(path: Path) -> dict[str, Any]:
    """Load a manual annotation JSON object with actionable errors."""
    if not path.exists():
        raise FileNotFoundError(
            f"Manual annotation not found: {path}. "
            "Create it with tools/manual_event_annotator/index.html."
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EventValidationError(f"Manual annotation is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise EventValidationError("Manual annotation root must be a JSON object")
    return payload


def _annotation_fps(payload: Mapping[str, Any], override: float | None) -> float:
    if override is not None:
        return validate_fps(override)
    return validate_fps(payload.get("fps", DEFAULT_FPS))


def _frames_total(payload: Mapping[str, Any]) -> int | None:
    value = payload.get("frames_total")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise EventValidationError("frames_total must be a positive integer when provided")
    return value


def normalize_annotation(
    payload: Mapping[str, Any],
    *,
    fps: float | None = None,
) -> tuple[float, list[NormalizedEvent]]:
    """Normalize all supplied events while preserving their declared order."""
    raw_events = payload.get("narrative_events")
    if not isinstance(raw_events, list):
        raise MissingNarrativeEventsError("narrative_events must be a JSON list")
    if not raw_events:
        raise MissingNarrativeEventsError(
            "narrative_events is empty; Stage 4 cannot invent rally events"
        )

    resolved_fps = _annotation_fps(payload, fps)
    total_frames = _frames_total(payload)
    events: list[NormalizedEvent] = []
    seen_ids: set[str] = set()
    previous_start = -1

    for index, raw_event in enumerate(raw_events):
        try:
            event = normalize_narrative_event(raw_event, resolved_fps)
        except EventValidationError as exc:
            raise EventValidationError(f"narrative_events[{index}]: {exc}") from exc

        if event.id in seen_ids:
            raise EventValidationError(f"duplicate event id: {event.id}")
        if event.frame_start < previous_start:
            raise EventValidationError(
                "narrative_events must be ordered chronologically by frame_range"
            )
        if total_frames is not None and event.frame_end >= total_frames:
            raise EventValidationError(
                f"event {event.id} ends at frame {event.frame_end}, "
                f"outside frames_total={total_frames}"
            )

        seen_ids.add(event.id)
        previous_start = event.frame_start
        events.append(event)

    return resolved_fps, events


def load_normalized_events(
    annotation_path: Path,
    *,
    fps: float | None = None,
) -> tuple[float, list[NormalizedEvent]]:
    """Load a file and return its validated FPS and normalized events."""
    payload = load_annotation(annotation_path)
    return normalize_annotation(payload, fps=fps)


def export_events(
    output_path: Path,
    events: list[NormalizedEvent],
    *,
    fps: float,
    annotation_path: Path,
) -> dict[str, object]:
    """Write the normalized Stage 4 payload after successful validation."""
    if not events:
        raise MissingNarrativeEventsError("Refusing to export an empty events list")
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "source_annotation": str(annotation_path),
        "fps": validate_fps(fps),
        "event_count": len(events),
        "events": [event.to_dict() for event in events],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return payload


def run_stage_4(
    annotation_path: Path,
    output_path: Path,
    *,
    fps: float | None = None,
) -> dict[str, object]:
    """Normalize a real annotation and export Stage 4 events."""
    resolved_fps, events = load_normalized_events(annotation_path, fps=fps)
    return export_events(
        output_path,
        events,
        fps=resolved_fps,
        annotation_path=annotation_path,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotation", type=Path, default=DEFAULT_ANNOTATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--fps",
        type=float,
        help="Override annotation FPS; otherwise use JSON fps or default 60",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = run_stage_4(args.annotation, args.output, fps=args.fps)
    except (FileNotFoundError, EventValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {payload['event_count']} events to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
