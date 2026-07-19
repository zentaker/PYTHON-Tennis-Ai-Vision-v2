from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.stage5b_v3.coordinate_audit import (
    BASELINE_FAR_Y_M,
    BASELINE_NEAR_Y_M,
    COURT_LENGTH_M,
    DOUBLES_WIDTH_M,
    SINGLES_WIDTH_M,
    audit_coordinates,
)


def test_regulation_convention_and_p1_homography_regression() -> None:
    assert (COURT_LENGTH_M, BASELINE_NEAR_Y_M, BASELINE_FAR_Y_M) == (23.77, -11.885, 11.885)
    assert (SINGLES_WIDTH_M, DOUBLES_WIDTH_M) == (8.23, 10.97)
    result = audit_coordinates(
        Path("data/clips/nivel_a2_01/homography.json"),
        Path("tests/fixtures/integration/p1_analytics_accepted"),
    )
    assert result["maximum_stored_recomputed_xy_difference_m"] < 1e-9
    by_id = {row["event_id"]: row for row in result["contacts"]}
    assert np.isclose(by_id["ev_001"]["distance_to_correct_baseline_m"], 1.1278333062650727)
    assert np.isclose(by_id["ev_003"]["distance_to_correct_baseline_m"], 8.02521461748285)
    assert not by_id["ev_003"]["plausible_player_zone"]
    assert by_id["ev_003"]["warning"]


def test_homography_changes_coordinate_metric(tmp_path: Path) -> None:
    source = Path("data/clips/nivel_a2_01/homography.json")
    payload = json.loads(source.read_text())
    payload["H_pixel_to_court"][0][2] += 0.01
    changed = tmp_path / "homography.json"
    changed.write_text(json.dumps(payload))
    original = audit_coordinates(source, Path("tests/fixtures/integration/p1_analytics_accepted"))
    perturbed = audit_coordinates(changed, Path("tests/fixtures/integration/p1_analytics_accepted"))
    assert perturbed["maximum_stored_recomputed_xy_difference_m"] != original["maximum_stored_recomputed_xy_difference_m"]


def test_top_visual_keeps_out_of_zone_audit_evidence() -> None:
    result = json.loads(Path("config/stage5b_v3/stage5b_v31_result.json").read_text())
    assert result["contacts_physically_plausible"] is False
    assert Path("docs/validation/assets/stage5b_v31_top_view.jpg").stat().st_size > 0
