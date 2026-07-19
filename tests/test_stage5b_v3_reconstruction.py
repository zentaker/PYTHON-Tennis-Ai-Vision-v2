from __future__ import annotations

from pathlib import Path

from src.stage5b_v3.reconstruction import reconstruct


FIXTURE = Path("tests/fixtures/stage5b_v3")
P1 = Path("tests/fixtures/integration/p1_analytics_accepted")


def run():
    return reconstruct(
        FIXTURE / "camera_model_refined.json",
        FIXTURE / "smoothed_trajectory_real.csv",
        Path("data/clips/nivel_a2_01/manual_annotation.json"),
        P1,
        Path("config/stage5b_v3/player_aware_v1.json"),
        seed=42,
        max_hypotheses=3,
    )


def test_real_fixture_reconstructs_vfr_segments_bounces_and_hypotheses() -> None:
    result = run()
    assert len(result["contacts"]) == 5
    assert len(result["segments"]) == 9
    assert len(result["hypotheses"]) == 3
    assert result["observations_consumed"] > 250
    assert all(row["z_m"] >= 0 for row in result["samples"])
    assert any(row["observed_or_interpolated"] == "interpolated" for row in result["samples"])
    assert len({row["timestamp_seconds"] for row in result["samples"]}) > 250
    for hypothesis in result["hypotheses"]:
        assert sum(anchor["z_m"] == 0 for anchor in hypothesis["anchors"]) == 5


def test_reconstruction_is_deterministic_and_reports_uncertainty() -> None:
    first, second = run(), run()
    assert first["checksum"] == second["checksum"]
    assert first["xyz_jsonl"] == second["xyz_jsonl"]
    assert all(row["uncertainty_z_m"] > 0 for row in first["samples"])
    assert all(row["ambiguity_status"] == "AMBIGUOUS" for row in first["samples"])


def test_stage5b_v3_has_no_analytics_dependency_or_event_specific_hardcoding() -> None:
    sources = list(Path("src/stage5b_v3").glob("*.py"))
    text = "\n".join(path.read_text() for path in sources)
    assert "src.analytics" not in text
    assert "ev_001" not in text and "ev_003" not in text
