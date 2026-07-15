"""Render a VFR-time Stage 4 timeline with visible point and range events."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt

from src.events.render_events_overlay import EVENT_COLORS, load_event_rows


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _matplotlib_color(event_type: str) -> tuple[float, float, float]:
    blue, green, red = EVENT_COLORS.get(event_type, EVENT_COLORS["unknown"])
    return red / 255.0, green / 255.0, blue / 255.0


def render_events_timeline(events_path: Path, output_path: Path) -> dict[str, object]:
    """Render every VFR event in order and keep zero-duration point events visible."""
    events = load_event_rows(events_path)
    figure, axis = plt.subplots(figsize=(15, 8.8), dpi=160)
    point_events = 0

    for row, event in enumerate(events):
        start = float(event["time_start_seconds"])
        end = float(event["time_end_seconds"])
        is_point = int(event["frame_start"]) == int(event["frame_end"])
        event_type = str(event["type"])
        color = _matplotlib_color(event_type)
        if is_point:
            point_events += 1
            axis.vlines(start, row - 0.32, row + 0.32, color=color, linewidth=5, zorder=3)
            axis.scatter([start], [row], color=[color], edgecolor="black", s=75, zorder=4)
        else:
            axis.barh(
                row,
                max(end - start, 0.000001),
                left=start,
                height=0.55,
                color=color,
                edgecolor="black",
                linewidth=0.7,
            )
            axis.vlines([start, end], row - 0.32, row + 0.32, color=color, linewidth=2)
        label = (
            f"{event['id']} · {event_type} · {event['player']}/{event['side']} · "
            f"frames {event['frame_start']}–{event['frame_end']}"
        )
        axis.text(end + 0.035, row, label, va="center", fontsize=8)

    axis.set_yticks(range(len(events)), [str(event["id"]) for event in events])
    axis.invert_yaxis()
    axis.set_xlabel("Tiempo VFR (segundos)")
    axis.set_ylabel("Evento")
    axis.set_title("Stage 4 A2 — Eventos humanos normalizados")
    axis.grid(axis="x", alpha=0.28)
    max_time = max(float(event["time_end_seconds"]) for event in events)
    axis.set_xlim(left=max(0.0, min(float(event["time_start_seconds"]) for event in events) - 0.4))
    axis.set_xlim(right=max_time + 1.6)

    table_rows = [
        [
            event["id"],
            event["type"],
            f"{event['player']}/{event['side']}",
            f"{event['frame_start']}–{event['frame_end']}",
            str(int(event["frame_end"]) - int(event["frame_start"]) + 1),
            f"{float(event['time_start_seconds']):.6f}–{float(event['time_end_seconds']):.6f}",
        ]
        for event in events
    ]
    table = axis.table(
        cellText=table_rows,
        colLabels=["ID", "Tipo", "Jugador/lado", "Frames", "Cantidad", "Tiempo VFR (s)"],
        cellLoc="center",
        bbox=[0.0, -0.57, 1.0, 0.43],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7.5)
    figure.subplots_adjust(left=0.08, right=0.98, top=0.93, bottom=0.39)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, bbox_inches="tight")
    plt.close(figure)
    return {
        "path": str(output_path),
        "event_count": len(events),
        "point_events": point_events,
        "multiframe_events": len(events) - point_events,
        "time_axis": "variable_frame_rate_seconds",
    }


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
    metadata = render_events_timeline(args.events, args.output)
    print(f"Event timeline written to {args.output}: {metadata}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
