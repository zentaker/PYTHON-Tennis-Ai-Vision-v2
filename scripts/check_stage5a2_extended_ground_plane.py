#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".artifacts/stage5a2-extended-ground-plane/output"
STATUS = "STAGE5A2_REJECTED_BY_HUMAN_GATE_EVIDENCE_INSUFFICIENT"


def require(value: bool, message: str) -> None:
    if not value:
        raise SystemExit(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = json.loads(
        (ROOT / "config/ground_plane_calibration/input_manifest.json").read_text()
    )
    for item in manifest["inputs"]:
        path = Path(item["path"])
        if not path.is_absolute():
            path = ROOT / path
        if path.is_file():
            require(digest(path) == item["sha256"], f"input/hash mismatch: {path}")
        else:
            require(
                Path(item["path"]) == Path(manifest["inputs"][0]["path"])
                and len(item["sha256"]) == 64,
                f"tracked input missing: {path}",
            )
    result = json.loads((ROOT / "config/ground_plane_calibration/stage5a2_result.json").read_text())
    player_report = json.loads(
        (ROOT / "config/ground_plane_calibration/player_ground_position_report.json").read_text()
    )
    uncertainty = json.loads(
        (ROOT / "config/ground_plane_calibration/calibration_uncertainty.json").read_text()
    )
    require(result["status"] == STATUS, "status mismatch")
    require(result["human_visual_approval"] == "rejected", "human rejection not recorded")
    require(
        result["refined_line_median_px"] <= 4 and result["refined_line_p95_px"] <= 10,
        "line gate failed",
    )
    require(result["model_lines_evaluated"] >= 8, "insufficient model-line evaluation")
    require(
        player_report["frames_processed"] == result["player_frames_processed"],
        "player count mismatch",
    )
    require(
        player_report["zero_identity_changes"] and player_report["zero_nonfinite_positions"],
        "invalid player output",
    )
    require(
        player_report["events"]["ev_003"]["baseline_distance_m"] > 5,
        "PARTIAL far-player blocker absent",
    )
    require(uncertainty["runs"] == 64 and len(uncertainty["points"]) >= 5, "uncertainty invalid")
    for name in (
        "court_line_overlay",
        "old_vs_refined_homography",
        "camera_homography_consistency",
        "player_foot_contact_sheet",
        "player_ground_top_view",
        "extrapolation_uncertainty",
    ):
        path = ROOT / f"docs/validation/assets/stage5a2_{name}.jpg"
        require(path.is_file() and 0 < path.stat().st_size < 2_000_000, f"invalid visual: {name}")
    v31 = json.loads((ROOT / "config/stage5b_v3/stage5b_v31_result.json").read_text())
    require(v31["status"] == "STAGE5B_V31_REJECTED_BY_HUMAN_GATE", "v3.1 rejection lost")
    print(f"status: {STATUS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
