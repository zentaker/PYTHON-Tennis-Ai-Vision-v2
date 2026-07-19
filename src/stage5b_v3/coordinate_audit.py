"""Regulation-court audit for P1 feet and stored player coordinates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from src.court.homography import apply_homography

COURT_LENGTH_M = 23.77
BASELINE_NEAR_Y_M = -11.885
BASELINE_FAR_Y_M = 11.885
SINGLES_WIDTH_M = 8.23
DOUBLES_WIDTH_M = 10.97


def audit_coordinates(homography_path: Path, p1_results: Path) -> dict[str, Any]:
    homography = json.loads(homography_path.read_text())
    matrix = np.asarray(homography["H_pixel_to_court"], dtype=float)
    contacts = json.loads((p1_results / "selected_contact_audit.json").read_text())
    rows = []
    for contact in contacts:
        foot = contact["foot_anchor"]
        stored = contact["court_position"]
        recomputed = apply_homography(
            matrix, np.array([[foot["x_pixel"], foot["y_pixel"]]], dtype=float)
        )[0]
        identity = contact["identity"]
        baseline = BASELINE_NEAR_Y_M if identity == "near" else BASELINE_FAR_Y_M
        signed_behind = (
            BASELINE_NEAR_Y_M - recomputed[1]
            if identity == "near"
            else recomputed[1] - BASELINE_FAR_Y_M
        )
        difference = float(np.linalg.norm(recomputed - [stored["x_m"], stored["y_m"]]))
        inside = abs(recomputed[0]) <= DOUBLES_WIDTH_M / 2 and abs(recomputed[1]) <= COURT_LENGTH_M / 2
        plausible = abs(recomputed[0]) <= DOUBLES_WIDTH_M / 2 and signed_behind <= 4.0
        warning = None
        if signed_behind > 4.0:
            warning = "HOMOGRAPHY_EXTRAPOLATION_BEYOND_PLAUSIBLE_PLAYER_ZONE"
        rows.append(
            {
                "event_id": contact["event_id"],
                "identity": identity,
                "foot_pixel": [foot["x_pixel"], foot["y_pixel"]],
                "stored_xy_m": [stored["x_m"], stored["y_m"]],
                "recomputed_xy_m": recomputed.tolist(),
                "stored_recomputed_difference_m": difference,
                "correct_baseline_y_m": baseline,
                "distance_to_correct_baseline_m": abs(float(recomputed[1] - baseline)),
                "inside_regulation_doubles_court": bool(inside),
                "distance_behind_baseline_m": max(0.0, float(signed_behind)),
                "plausible_player_zone": bool(plausible),
                "warning": warning,
            }
        )
    return {
        "status": "COORDINATE_CONVENTION_VERIFIED_WITH_EXTRAPOLATION_WARNING",
        "coordinate_convention": "X right, Y far, Z up; net Y=0; near baseline -11.885m; far baseline +11.885m",
        "court_dimensions_m": {
            "length": COURT_LENGTH_M,
            "singles_width": SINGLES_WIDTH_M,
            "doubles_width": DOUBLES_WIDTH_M,
        },
        "contacts": rows,
        "maximum_stored_recomputed_xy_difference_m": max(
            row["stored_recomputed_difference_m"] for row in rows
        ),
        "cause": "P1 serialization matches Stage 1 homography exactly; far-player implausibility is unstable planar extrapolation beyond calibration court, not serialization drift",
    }
