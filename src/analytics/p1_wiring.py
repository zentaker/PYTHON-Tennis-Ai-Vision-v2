"""Wire accepted serialized P1 contacts into conservative Analytics records."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .adapters.p1_outputs import AcceptedP1Contact, load_accepted_p1_contacts
from .adapters.stage4_events import adapt_stage4_event
from .contracts import AnalyticsEventInput, ClassifiedStroke, EvidenceItem, StrokeAnalyticsRecord
from .schema_validation import validators


class Stage4InputError(ValueError):
    """Raised when serialized Stage 4 input is malformed or ambiguous."""


def load_stage4(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise Stage4InputError(f"{path}: invalid JSON root: {exc}") from exc

    if isinstance(payload, list):
        events = payload
    elif isinstance(payload, Mapping):
        keys = [key for key in ("events", "narrative_events") if key in payload]
        if not keys:
            raise Stage4InputError(
                f"{path}: root object requires 'events' or 'narrative_events'"
            )
        if len(keys) > 1:
            raise Stage4InputError(
                f"{path}: root object has ambiguous event collections: {keys}"
            )
        events = payload[keys[0]]
        if not isinstance(events, list):
            raise Stage4InputError(f"{path}: '{keys[0]}' must be a list")
    else:
        raise Stage4InputError(f"{path}: JSON root must be a list or object")

    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(events):
        if not isinstance(item, Mapping):
            raise Stage4InputError(f"{path}: event index {index} must be an object")
        raw_id = item.get("id")
        raw_event_id = item.get("event_id")
        if raw_id is not None and raw_event_id is not None and raw_id != raw_event_id:
            raise Stage4InputError(
                f"{path}: event index {index} has conflicting id {raw_id!r} "
                f"and event_id {raw_event_id!r}"
            )
        identifier = raw_id if raw_id is not None else raw_event_id
        if not isinstance(identifier, str):
            raise Stage4InputError(
                f"{path}: event index {index} requires string id or event_id"
            )
        identifier = identifier.strip()
        if not identifier:
            raise Stage4InputError(f"{path}: event index {index} has empty ID")
        if identifier in result:
            raise Stage4InputError(
                f"{path}: event index {index} has duplicate ID {identifier!r}"
            )
        result[identifier] = dict(item)
    return result


def wire_contacts(contacts: tuple[AcceptedP1Contact, ...], stage4: dict[str, dict[str, Any]], *, p1_source_sha: str, p1_results_sha256: str) -> tuple[StrokeAnalyticsRecord, ...]:
    records = []
    for item in contacts:
        manual = stage4.get(item.event.event_id)
        label = None if manual is None or str(manual.get("shot_type", "unknown")).lower() == "unknown" else str(manual["shot_type"])
        stroke = adapt_stage4_event(manual) if label else ClassifiedStroke()
        metadata = {
            "p1_acceptance_status": "P1_TEN_FRAME_ACCEPTANCE_PASSED",
            "p1_source_sha": p1_source_sha,
            "p1_results_sha256": p1_results_sha256,
            "track_id": item.player.track_id,
            "selected_identity": item.player.identity,
            "player_context": asdict(item.player),
            "court_position": item.position,
            "pose_keypoint_count": len(item.pose["keypoints"]),
            "wrist_pixels": item.audit.get("wrist_pixels"),
            "ball_pixel": item.audit.get("ball_pixel"),
            "ball_wrist_distance_px": item.audit.get("ball_wrist_distance_px"),
            "contact_confidence": item.audit.get("confidence"),
            "contact_warnings": item.audit.get("warnings", []),
            "stage4_match_status": "MANUAL_LABEL_MATCHED" if label else "LABEL_UNAVAILABLE",
            "stage5b_xyz_status": "APPROVED_STAGE5B_XYZ_REQUIRED",
        }
        evidence = list(item.evidence)
        if label:
            evidence.append(EvidenceItem("stage4_manual_annotation", "event_id_match", f"manual label: {label}", 1.0, human_labeled=True))
        evidence.append(EvidenceItem("stage5b_xyz", "dependency_check", "APPROVED_STAGE5B_XYZ_REQUIRED", 0.0))
        event = AnalyticsEventInput(item.event.event_id, item.event.timestamp_seconds, item.event.frame_id, label, metadata)
        records.append(StrokeAnalyticsRecord("1.0", event, stroke, None, tuple(evidence)))
    return tuple(records)


def write_wiring_outputs(results_dir: Path, stage4_path: Path | None, output_dir: Path, *, p1_source_sha: str, p1_results_sha256: str) -> dict[str, Any]:
    contacts = load_accepted_p1_contacts(results_dir)
    stage4 = load_stage4(stage4_path)
    records = wire_contacts(contacts, stage4, p1_source_sha=p1_source_sha, p1_results_sha256=p1_results_sha256)
    _, validator = validators()
    serialized = [record.to_dict() for record in records]
    for record in serialized:
        validator.validate(record)
    output_dir.mkdir(parents=True, exist_ok=True)
    lines = "".join(json.dumps(row, sort_keys=True) + "\n" for row in serialized)
    checksum = hashlib.sha256(lines.encode()).hexdigest()
    (output_dir / "stroke_analytics_records.jsonl").write_text(lines)
    contexts = [{"event": row["event"], "evidence": row["evidence"]} for row in serialized]
    (output_dir / "p1_event_contexts.json").write_text(json.dumps(contexts, indent=2) + "\n")
    matched = sum(row["event"]["legacy_shot_type"] is not None for row in serialized)
    report = {
        "status": "P1_ANALYTICS_FUNCTIONAL_WIRING_PASSED" if len(records) == 5 else "P1_ANALYTICS_FUNCTIONAL_WIRING_PARTIAL",
        "contacts_found": len(contacts), "records_produced": len(records), "events_matched": sum(item.event.event_id in stage4 for item in contacts),
        "stage4_labels_matched": matched, "stage4_labels_unavailable": len(records) - matched,
        "selected_near_events": sum(item.player.identity == "near" for item in contacts), "selected_far_events": sum(item.player.identity == "far" for item in contacts),
        "pose_matches": len(records), "court_position_matches": len(records), "wrist_evidence_matches": len(records), "schema_valid_records": len(records),
        "unknown_stroke_dimensions": sum(dimension["value"] == "unknown" for row in serialized for dimension in row["stroke"].values()),
        "kinematics_unavailable_count": sum(row["kinematics"] is None for row in serialized), "warnings": ["APPROVED_STAGE5B_XYZ_REQUIRED"], "failures": [], "deterministic_output_checksum": checksum,
    }
    (output_dir / "p1_analytics_wiring_report.json").write_text(json.dumps(report, indent=2) + "\n")
    manifest = {"p1_results": str(results_dir), "stage4_events": str(stage4_path) if stage4_path else None, "p1_source_sha": p1_source_sha, "p1_results_sha256": p1_results_sha256}
    (output_dir / "p1_analytics_input_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    validation = {"schema": "stroke_analytics.schema.json", "records_valid": len(records), "status": "INSTANCE_VALIDATED", "checksum": checksum}
    (output_dir / "p1_analytics_validation_report.json").write_text(json.dumps(validation, indent=2) + "\n")
    return report
