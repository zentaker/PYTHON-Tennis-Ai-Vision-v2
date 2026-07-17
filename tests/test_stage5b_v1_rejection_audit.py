from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_v1_frame_gate_was_not_24_real_solves() -> None:
    source = (ROOT / "scripts/stage5b_a2.py").read_text(encoding="utf-8")
    assert 'base["cost"] + index * 1e-3' in source
    assert "max_nfev: int = 8" in (ROOT / "src/reconstruction3d/joint_fit.py").read_text(
        encoding="utf-8"
    )


def test_v1_rejection_is_documented_without_deleting_outputs() -> None:
    report = (ROOT / "docs/levels/level_a2/stage_5b_v1_rejection_report.md").read_text(
        encoding="utf-8"
    )
    assert "REJECTED_BY_HUMAN_GATE" in report
    assert "0.354 m" in report
    assert "sin sobrescritura" in report
