# P1 Analytics functional wiring track

- Upstream gate: `P1_TEN_FRAME_ACCEPTANCE_PASSED`.
- Wiring gate: `P1_ANALYTICS_FUNCTIONAL_WIRING_PASSED`.
- Accepted contacts / Analytics records: 5 / 5.
- Real timestamps, tracks, poses, positions, wrist evidence: 5 each.
- Stage 4 event matches: 5; informative labels: 1; unavailable labels: 4.
- Stroke classification: conservative Stage 4 mapping only.
- Unknown stroke dimensions: 23 of 25.
- Hitting hand: unknown for all records.
- Spin inference: not implemented.
- Kinematics: null; real ball speed unavailable.
- Blocker: `APPROVED_STAGE5B_XYZ_REQUIRED`.
- Full rally: not validated.
- GPU calls / cloud calls / spend: 0 / 0 / 0.

The reduced regression fixture is
`tests/fixtures/integration/p1_analytics_accepted/`. It contains only machine-readable
data needed to reproduce the five-event wiring and records its source checksums.

Pre-merge hardening makes Stage 4 ingestion fail closed: malformed structures and
duplicate, missing, empty, or conflicting event IDs are rejected instead of normalized
or overwritten. The historical `scripts/check_p1_analytics_integration.py` is retained
as an archival audit of its original branch. Active validation is branch-agnostic via
`scripts/check_p1_analytics_functional_wiring.py` and the existing CI job. The checker
reproduces and schema-validates all five records and verifies every fixture-manifest
hash and the deterministic output checksum. GPU calls, cloud calls, and spend remain
zero. Stage 5B state is unchanged.
