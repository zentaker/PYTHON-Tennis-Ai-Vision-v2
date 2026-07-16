"""Metric-based Stage 5A.1 readiness decisions."""

from tools.vertical_reference_app.evaluation import classify_readiness


def test_readiness_statuses_are_not_hardcoded() -> None:
    passed = {"geometry": True, "jitter": True}
    assert classify_readiness(passed, 2, 4, 90) == "READY_FOR_STAGE_5B"
    assert classify_readiness({"geometry": True, "jitter": False}, 2, 4, 90) == "MARGINAL_VERTICAL_CALIBRATION"
    assert classify_readiness({"geometry": True, "jitter": False}, 8, 20, 20) == "STILL_NEEDS_VERTICAL_REFERENCE"
    assert classify_readiness({}, 0, 0, 100, invalid_reference=True) == "INVALID_HUMAN_REFERENCE"


def test_real_reference_report_has_explicit_criteria() -> None:
    import json
    from pathlib import Path

    path = Path("outputs/nivel_a2_01/stage_5a1/readiness_report.json")
    if not path.exists():
        return
    report = json.loads(path.read_text())
    assert report["status"] in {"READY_FOR_STAGE_5B", "MARGINAL_VERTICAL_CALIBRATION", "STILL_NEEDS_VERTICAL_REFERENCE", "INVALID_HUMAN_REFERENCE"}
    assert "passed_criteria" in report and "failed_criteria" in report
