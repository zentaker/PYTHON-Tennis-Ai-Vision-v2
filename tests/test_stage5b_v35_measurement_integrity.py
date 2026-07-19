from __future__ import annotations

import json
from pathlib import Path

from src.stage5b_v3.event_time_candidates import declared_event_frames
from src.stage5b_v3.measurement_integrity import audit_rows, provenance_graph

ROOT = Path(__file__).parents[1]
OUT = ROOT / ".artifacts/stage5b-v35-observation-conditioned/output"


def test_correlated_sources_and_uncertainty_floor() -> None:
    graph = provenance_graph()
    assert graph["raw"]["independent"]
    assert graph["smoothed"]["correlation_group"] == graph["p1_contact"]["correlation_group"]
    assert "uncertainty floor" in graph["covariance_policy"]


def test_duplicate_frozen_and_suspicious_classification() -> None:
    rows = [
        {
            "frame_id": 1,
            "timestamp_seconds": 0.0,
            "raw_pixel": [1, 1],
            "smoothed_pixel": [1, 1],
            "confidence": 0.9,
            "source": "detected",
        },
        {
            "frame_id": 2,
            "timestamp_seconds": 0.01,
            "raw_pixel": [1, 1],
            "smoothed_pixel": [1, 1],
            "confidence": 0.4,
            "source": "detected",
        },
        {
            "frame_id": 3,
            "timestamp_seconds": 0.02,
            "raw_pixel": [1000, 1],
            "smoothed_pixel": [1000, 1],
            "confidence": 0.9,
            "source": "detected",
        },
    ]
    audited = audit_rows(rows, [0.0, 0.02])
    assert audited[1]["measurement_status"] == "MEASUREMENT_DUPLICATE_OR_FROZEN"
    assert any("kinematically_suspicious" in row["warnings"] for row in audited)


def test_timestamps_and_ranges_are_preserved() -> None:
    event = {"frame_start": 10, "frame_end": 12, "frame_range": [10, 11, 12]}
    assert declared_event_frames(event) == [10, 11, 12]
    output = json.loads((OUT / "stage5b_v35_measurement_integrity.json").read_text())
    assert output["report"]["observations_inventoried"] == 314
    assert output["report"]["event_ranges_respected"]


def test_flight_focus_anomalies_are_reported_not_removed() -> None:
    output = json.loads((OUT / "stage5b_v35_measurement_integrity.json").read_text())
    assert set(output["report"]["audited_segments"]) == {
        "flight_03",
        "flight_05",
        "flight_07",
        "flight_09",
    }
    assert sum(output["report"]["status_counts"].values()) == 314


def test_deterministic_audit() -> None:
    output = json.loads((OUT / "stage5b_v35_run_report.json").read_text())
    assert len(output["deterministic_checksum"]) == 64
