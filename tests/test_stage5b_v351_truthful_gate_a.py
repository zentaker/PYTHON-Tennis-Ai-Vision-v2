from __future__ import annotations

import csv
import json
from pathlib import Path

from src.stage5b_v3.measurement_integrity import audit_rows
from src.stage5b_v3.observation_conditioned_edges import score_edge
from src.geometry.camera_model import CameraModel

ROOT = Path(__file__).parents[1]
OUT = ROOT / ".artifacts/stage5b-v351-truthful-gate-a/output"


def test_gate_d_is_dynamic_and_anomalies_change_policy() -> None:
    rows = [
        {"frame_id": 1, "timestamp_seconds": 0.0, "raw_pixel": [1, 1], "smoothed_pixel": [1, 1], "confidence": 0.9, "source": "detected"},
        {"frame_id": 2, "timestamp_seconds": 0.01, "raw_pixel": [1, 1], "smoothed_pixel": [1, 1], "confidence": 0.9, "source": "detected"},
        {"frame_id": 3, "timestamp_seconds": 0.02, "raw_pixel": [1000, 1], "smoothed_pixel": [1000, 1], "confidence": 0.9, "source": "detected"},
    ]
    audited = audit_rows(rows, [0.0])
    assert audited[1]["weight_multiplier"] < 1.0
    assert audited[2]["weight_multiplier"] < 1.0
    assert audited[1]["usable"]


def test_invalid_observation_is_not_used_by_edge() -> None:
    camera = CameraModel.read_json(ROOT / "tests/fixtures/stage5b_v3/camera_model_refined.json")
    edge = score_edge(camera, {"timestamp_seconds": 0.0, "xyz": [0, -10, 1]}, {"timestamp_seconds": 1.0, "xyz": [0, 10, 0]}, [{"frame_id": 1, "timestamp_seconds": 0.1, "pixel": [1000, 700], "usable": False, "weight_multiplier": 0.0, "sigma_px": 50.0}])
    assert edge["observations_invalid"] == 1
    assert edge["observations_usable"] == 0


def test_body_fields_are_truthful_and_no_false_shoulder() -> None:
    candidates = json.loads((OUT / "stage5b_v351_contact_candidates.json").read_text())
    body = next(item for item in candidates if item.get("body_method_status"))
    assert body["body_method_status"] == "BODY_CONTACT_APPROXIMATE"
    assert body["body_candidate"]["shoulder_xyz"] is None
    assert "ground_anchor_xyz" in body["body_candidate"]


def test_event_candidates_use_declared_alternatives_without_pose_copy() -> None:
    candidates = json.loads((OUT / "stage5b_v351_event_candidates.json").read_text())
    assert len(candidates) >= 10
    alternate = [row for row in candidates if row["frame_id"] in (288, 435)]
    assert alternate and any("POSE_UNAVAILABLE" in row["warnings"] for row in alternate)


def test_linear_drag_is_not_a_false_model_alias() -> None:
    source = (ROOT / "src/stage5b_v3/observation_conditioned_edges.py").read_text()
    assert "LINEAR_DRAG_NOT_IMPLEMENTED" in source
    assert all(model["model"] == "MODEL_G" for edge in json.loads((OUT / "stage5b_v351_edge_costs.json").read_text()) for model in edge.get("models", [{"model": "MODEL_G"}]))


def test_new_nodes_do_not_load_v34_selected_nodes() -> None:
    source = (ROOT / "scripts/run_stage5b_v351_truthful_gate_a.py").read_text()
    assert "stage5b_v34_event_nodes" not in source


def test_multiple_global_hypotheses_and_gate_b_block() -> None:
    hypotheses = json.loads((OUT / "stage5b_v351_global_hypotheses.json").read_text())
    report = json.loads((OUT / "stage5b_v351_run_report.json").read_text())
    assert len(hypotheses) >= 2
    assert report["gate_b_executed"] is False


def test_residual_evidence_has_all_accounted_rows_and_worst_frames() -> None:
    with (OUT / "stage5b_v351_frame_residuals.csv").open(newline="") as handle:
        assert sum(1 for _ in csv.DictReader(handle)) == 314
    worst = json.loads((OUT / "stage5b_v351_worst_residuals.json").read_text())
    assert len(worst["worst_usable_frames"]) == 20


def test_real_frame_visual_manifest_is_nonempty() -> None:
    for name in ("measurement_integrity", "contact_time_windows", "contact_candidate_geometry", "global_hypotheses", "reprojection_contact_sheet", "worst_reprojection_frames", "top_view", "side_view", "holdout", "per_segment_metrics"):
        path = ROOT / f"docs/validation/assets/stage5b_v351_{name}.jpg"
        assert path.stat().st_size > 1000
