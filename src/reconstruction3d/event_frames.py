"""Exact VFR event-frame candidates and the required 24-combination enumeration."""

from __future__ import annotations

import itertools
from typing import Any


def candidate_frames(event: dict[str, Any]) -> list[int]:
    start, end = int(event["frame_start"]), int(event["frame_end"])
    return list(range(start, end + 1))


def enumerate_event_frame_combinations(events: list[dict[str, Any]]) -> list[dict[str, int]]:
    multi = [e for e in events if int(e["frame_end"]) > int(e["frame_start"])]
    fixed = {str(e["id"]): int(e["frame_start"]) for e in events if e not in multi}
    combos: list[dict[str, int]] = []
    for values in itertools.product(*(candidate_frames(e) for e in multi)):
        combo = dict(fixed)
        combo.update({str(e["id"]): int(v) for e, v in zip(multi, values, strict=True)})
        combos.append(dict(sorted(combo.items())))
    return combos
