"""Evaluate the existing human Stage 5A.1 reference without changing its clicks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from tools.vertical_reference_app.core import VerticalReferenceSession
from tools.vertical_reference_app.evaluation import evaluate_vertical_calibration, render_vertical_overlays, write_candidate_csv


ROOT = Path(__file__).resolve().parents[1]
CLIP = ROOT / "data" / "clips" / "nivel_a2_01"
OUT = ROOT / "outputs" / "nivel_a2_01" / "stage_5a1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    session = VerticalReferenceSession("nivel_a2_01")
    reference_payload = json.loads((CLIP / "vertical_reference.json").read_text(encoding="utf-8"))
    references = reference_payload["references"]
    if [item["id"] for item in references] != ["net_center_base", "net_center_top", "net_post_base", "net_post_top"]:
        raise ValueError("vertical_reference.json does not contain the four expected references")
    evaluation = evaluate_vertical_calibration(session.camera, session.candidates, session.homography, references)
    OUT.mkdir(parents=True, exist_ok=True)
    selected_model = evaluation["selected_model"]
    selected_payload = selected_model.to_dict(
        clip_id="nivel_a2_01",
        status=evaluation["status"],
        calibration_method="ASSUMPTION_BASED_MONOCULAR_CALIBRATION_WITH_HUMAN_VERTICAL_REFERENCE",
        source_vertical_reference_sha256=sha256(CLIP / "vertical_reference.json"),
        source_homography_sha256=sha256(CLIP / "homography.json"),
        initial_candidate_id=evaluation["selected"]["candidate_id"],
        refined_candidate_id=evaluation["selected"]["candidate_id"],
        metrics=evaluation["metrics"],
        uncertainty={"jitter": evaluation["jitter"], "sensitivity_before_px": evaluation["sensitivity_before_px"], "sensitivity_after_px": evaluation["sensitivity_after_px"]},
        criteria=evaluation["criteria"],
    )
    (OUT / "camera_model_refined.json").write_text(json.dumps(selected_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_candidate_csv(OUT / "vertical_candidate_comparison.csv", evaluation["candidate_results"])
    (OUT / "vertical_jitter_report.json").write_text(json.dumps(evaluation["jitter"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report = {key: value for key, value in evaluation.items() if key not in {"selected_model"}}
    report.update({"clip_id": "nivel_a2_01", "vertical_reference_sha256": sha256(CLIP / "vertical_reference.json"), "source_homography_sha256": sha256(CLIP / "homography.json"), "recommendation": evaluation["recommendation"]})
    (OUT / "vertical_calibration_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    readiness = {"status": evaluation["status"], "passed_criteria": evaluation["criteria"]["passed"], "failed_criteria": evaluation["criteria"]["failed"], "ground_errors": evaluation["metrics"]["ground"], "vertical_errors": evaluation["metrics"]["vertical"], "vertical_reprojection": evaluation["metrics"]["vertical_reprojection"], "sensitivity_before_px": evaluation["sensitivity_before_px"], "sensitivity_after_px": evaluation["sensitivity_after_px"], "improvement_percentage": evaluation["improvement_percentage"], "uncertainty": evaluation["jitter"], "recommendation": evaluation["recommendation"], "selected_candidate_id": evaluation["selected"]["candidate_id"], "stage_5b_started": False}
    (OUT / "readiness_report.json").write_text(json.dumps(readiness, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    render_vertical_overlays(CLIP / "reference_frame.png", OUT / "vertical_calibration_overlay.png", OUT / "vertical_calibration_closeup.png", selected_model, session.homography, references)
    print(json.dumps({"status": evaluation["status"], "selected_candidate": evaluation["selected"]["candidate_id"], "sensitivity_after_px": evaluation["sensitivity_after_px"], "failed_criteria": evaluation["criteria"]["failed"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
