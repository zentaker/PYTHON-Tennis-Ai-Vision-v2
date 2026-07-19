from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from src.stage5b_v3.reconstruction import _load_ball


FIXTURE = Path("tests/fixtures/stage5b_v3")


def test_real_fixture_manifest_and_vfr_gap_evidence() -> None:
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    for filename, checksum in manifest["files"].items():
        assert hashlib.sha256((FIXTURE / filename).read_bytes()).hexdigest() == checksum
    with (FIXTURE / "smoothed_trajectory_real.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    times = [float(row["timestamp_seconds"]) for row in rows]
    deltas = {round(b - a, 6) for a, b in zip(times, times[1:], strict=False)}
    assert len(deltas) > 1
    assert any(not row["x_smooth"] for row in rows)
    longest_gap = current_gap = 0
    for row in rows:
        current_gap = current_gap + 1 if not row["x_smooth"] else 0
        longest_gap = max(longest_gap, current_gap)
    assert longest_gap >= 8


def test_ball_outlier_is_rejected(tmp_path: Path) -> None:
    with (FIXTURE / "smoothed_trajectory_real.csv").open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = reader.fieldnames
    observed = next(row for row in rows if row["x_smooth"])
    observed["is_outlier"] = "true"
    path = tmp_path / "track.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(observed)
    assert _load_ball(path) == []


def test_v1_and_v2_historical_modules_remain_present() -> None:
    assert Path("src/reconstruction3d/joint_fit.py").is_file()
    assert Path("src/reconstruction3d_v2/combination_fit.py").is_file()
