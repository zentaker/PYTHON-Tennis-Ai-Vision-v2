# P1 to Analytics functional wiring

Status: `P1_ANALYTICS_FUNCTIONAL_WIRING_PASSED`.

The read-only Analytics adapter consumed the accepted P1 GPU-retest serialization at
checksum `a2e2c138cff1076b9531c24d690a48a44b993a8168e3b52a5d274a50ed11feba`.
It associated all five accepted contacts with their real stored timestamps, selected
tracks, 133-keypoint poses, court positions, and ball-to-wrist evidence. The adapter
does not import or mutate `src.player_perception`.

The real execution produced five schema-valid `StrokeAnalyticsRecord` objects. Stage 4
matched all five event IDs, but only `ev_001` has an informative manual label (`saque`);
the other four explicitly remain unavailable. The conservative adapter therefore maps
only serve side and serve contact mode. Hitting hand and spin remain unknown unless
explicit evidence is added later.

Kinematics is `null` for every record. Real ball speed is not available, no pixel or
planar measurement is presented as 3D speed, and the dependency remains
`APPROVED_STAGE5B_XYZ_REQUIRED`. Full-rally processing is not validated.

Reproduction:

```bash
uv run python scripts/run_p1_analytics_wiring.py \
  --p1-results <accepted-p1-results-directory> \
  --stage4-events data/clips/nivel_a2_01/manual_annotation.json \
  --output-dir .artifacts/p1-analytics-functional-wiring/output \
  --p1-source-sha ec24ac0f34f787b6b86258076186c7f90c2b2c4e \
  --p1-results-sha256 a2e2c138cff1076b9531c24d690a48a44b993a8168e3b52a5d274a50ed11feba
```

The execution made zero GPU or cloud calls and generated zero spend.

## Pre-merge hardening

Stage 4 input now fails closed. Only a root event list or an object containing exactly
one `events` or `narrative_events` list is accepted. Malformed roots, non-object event
items, missing or empty identifiers, conflicting `id`/`event_id` values, and duplicate
event identifiers are rejected with file and event-index context; duplicates are never
silently overwritten.

`scripts/check_p1_analytics_integration.py` remains an archival audit of the historical
coexistence branch. The active, branch-agnostic validation is
`scripts/check_p1_analytics_functional_wiring.py`; it verifies the recorded result,
fixture hashes, package isolation, five-record reproduction, JSON Schema validity, and
the deterministic checksum. It runs in the existing CI workflow. Hardening used zero
GPU calls, zero cloud calls, and zero spend.
