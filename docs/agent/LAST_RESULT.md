# Last result

- Status: `STAGE5A2B_REJECTED_BY_HUMAN_GATE_TRACKER_INVALID`.
- Contact-frame visual gate passed 5/5; near/far identity correct, zero visible switches.
- Temporal validation rejected: 143.144 m/s is optical-flow drift, not real movement.
- 137 real LSD segments; 61 supported / 76 rejected; nine painted model families supported.
- Eight correlated calibration families; 305 frames-evento across five ±30 windows.
- ev_003/ev_007 feet are visually on ground at 7.514/6.431 m behind baseline, but both
  remain unresolved because optical-flow speed diagnostics reach impossible values.
- Stage 5A.2: 31-frame temporal background, 10 court lines, 64 uncertainty runs,
  five P1 player frames, CPU only.
- Human visual approval rejected: clipped/mischaracterized visuals, correlated geometry,
  incomplete uncertainty, no temporal support, and an unjustified 5 m heuristic.
- V1 / v2: rejected by human gate / rejected by human gate.
- Five P1 contacts, nine flights, five bounce constraints, three hypotheses.
- 314 unique ball observations and 322 schema-valid segment samples.
- V3.1 resolved/ambiguous flights: 9/0; 9 sensitivity reruns.
- Baseline median/p95: 25.2663/68.6564 px; optimized: 6.7430/27.1056 px.
- Blockers: p95 gate and implausible far-player homography extrapolation.
- Human visual approval: rejected for implausible contacts/far coordinates, p95,
  audit-only homography, incomplete ambiguity comparison, and doubtful flights.
- Analytics / real 3D speed: blocked / unavailable.
- Stage 5C / Stage 6: not started / not started.
- Cloud calls / GPU calls / spend: 0 / 0 / 0.
