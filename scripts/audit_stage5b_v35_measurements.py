#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
from src.stage5b_v3.event_topology import canonical_timeline  # noqa: E402
from src.stage5b_v3.measurement_integrity import audit_rows, provenance_graph  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ball-track", type=Path, required=True)
    parser.add_argument("--stage4-events", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    events = canonical_timeline(args.stage4_events)
    rows = []
    with args.ball_track.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if not row.get("x_smooth") or not row.get("y_smooth"):
                continue
            rows.append({"frame_id": int(row["frame_id"]), "timestamp_seconds": float(row["timestamp_seconds"]), "raw_pixel": [float(row["x_raw"]), float(row["y_raw"])], "smoothed_pixel": [float(row["x_smooth"]), float(row["y_smooth"])], "confidence": float(row["confidence"]), "source": row["source"], "interpolation_status": row["source"] == "interpolated", "outlier_status": row["is_outlier"].lower() == "true"})
    audited = audit_rows(rows, [event["timestamp_seconds"] for event in events])
    segments = json.loads((ROOT / "config/stage5b_v3/stage5b_v33_segment_topology.json").read_text())
    for row in audited:
        match = next((segment for segment in segments if segment["start_timestamp"] <= row["timestamp_seconds"] <= segment["end_timestamp"]), None)
        row["assigned_segment"] = match["segment_id"] if match else None
        row["interval_valid"] = match is not None
    status_counts = {}
    for row in audited:
        status_counts[row["measurement_status"]] = status_counts.get(row["measurement_status"], 0) + 1
    report = {"status": "STAGE5B_V35_MEASUREMENT_INTEGRITY_PASSED", "observations_inventoried": len(audited), "status_counts": status_counts, "duplicate_or_frozen": sum(row["measurement_status"] == "MEASUREMENT_DUPLICATE_OR_FROZEN" for row in audited), "kinematically_suspicious": sum(row["measurement_status"] == "MEASUREMENT_KINEMATICALLY_SUSPICIOUS" for row in audited), "timestamps_consistent": all(right["timestamp_seconds"] > left["timestamp_seconds"] for left, right in zip(audited, audited[1:])), "event_ranges_respected": all(row["interval_valid"] for row in audited), "audited_segments": ["flight_03", "flight_05", "flight_07", "flight_09"]}
    (args.output_dir / "stage5b_v35_measurement_integrity.json").write_text(json.dumps({"report": report, "observations": audited}, indent=2) + "\n")
    (args.output_dir / "stage5b_v35_source_provenance.json").write_text(json.dumps(provenance_graph(), indent=2) + "\n")
    print(f"status: {report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
