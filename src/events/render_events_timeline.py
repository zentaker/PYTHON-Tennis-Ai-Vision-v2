"""Render a static timeline from normalized Stage 4 events."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt

from src.events.render_events_overlay import EVENT_COLORS, load_event_rows


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _matplotlib_color(event_type: str) -> tuple[float, float, float]:
    blue, green, red = EVENT_COLORS.get(event_type, EVENT_COLORS["unknown"])
    return red / 255.0, green / 255.0, blue / 255.0


def render_events_timeline(events_path: Path, output_path: Path) -> None:
    """Render one row per supplied event, preserving chronological order."""
    events = load_event_rows(events_path)
    height = max(3.5, 0.55 * len(events) + 1.8)
    figure, axis = plt.subplots(figsize=(12, height), dpi=160)

    for row, event in enumerate(events):
        start = float(event["time_start_seconds"])
        end = float(event["time_end_seconds"])
        duration = max(end - start, 0.01)
        event_type = str(event["type"])
        axis.barh(
            row,
            duration,
            left=start,
            height=0.55,
            color=_matplotlib_color(event_type),
        )
        label = f"{event['id']} · {event_type} · {event['player']} · {event['shot_type']}"
        axis.text(start + duration + 0.015, row, label, va="center", fontsize=8)

    axis.set_yticks(range(len(events)), [str(event["id"]) for event in events])
    axis.invert_yaxis()
    axis.set_xlabel("Tiempo (segundos)")
    axis.set_ylabel("Evento")
    axis.set_title("Stage 4 - Eventos manuales normalizados")
    axis.grid(axis="x", alpha=0.3)
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--events",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "stage_4" / "events.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "stage_4" / "events_timeline.png",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    render_events_timeline(args.events, args.output)
    print(f"Event timeline written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
