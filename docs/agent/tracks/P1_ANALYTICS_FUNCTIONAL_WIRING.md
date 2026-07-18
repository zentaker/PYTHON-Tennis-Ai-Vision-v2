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
