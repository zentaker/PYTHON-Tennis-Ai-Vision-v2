#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.stage5b_v3.coordinate_audit import audit_coordinates  # noqa: E402


def main() -> int:
    expected = json.loads((ROOT / "config/stage5b_v3/coordinate_audit_result.json").read_text())
    actual = audit_coordinates(
        ROOT / "data/clips/nivel_a2_01/homography.json",
        ROOT / "tests/fixtures/integration/p1_analytics_accepted",
    )
    if actual != expected:
        raise SystemExit("coordinate audit result mismatch")
    if actual["maximum_stored_recomputed_xy_difference_m"] > 1e-9:
        raise SystemExit("P1 stored/recomputed coordinate mismatch")
    if not any(not row["plausible_player_zone"] for row in actual["contacts"] if row["identity"] == "far"):
        raise SystemExit("far-player extrapolation was not detected")
    print("status: STAGE5B_V31_COORDINATE_AUDIT_VALIDATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
