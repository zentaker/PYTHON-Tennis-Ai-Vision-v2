# Stage 5B v3 player-aware candidate report

Status: `STAGE5B_V3_PLAYER_AWARE_CANDIDATE_READY_FOR_HUMAN_GATE`.

The real Level A2 execution consumed five accepted P1 contacts and 314 unique Stage 3
ball observations with VFR timestamps. It reconstructed nine event-delimited flights,
constrained five bounces to Z=0, evaluated three deterministic depth hypotheses, and
produced 322 schema-valid XYZ segment samples. Negative-Z violations: zero.

Median reprojection residual is 25.2663 px and p95 is 68.6564 px. Contact ball-ray
residuals are numerical zero; player-contact distances, wrist choice, wrist/ball pixel
distance, height, confidence, and warnings remain in the contact audit. All nine flights
remain ambiguous because alternative monocular contact depths are materially different.
Uncertainty is carried on every sample rather than hidden.

XYZ checksum: `6312b67a295f8ff9032e876b2fd895fede9a3282bfafe956215fe9fdb8cce618`.

This is not `STAGE5B_APPROVED` or `APPROVED_STAGE5B_XYZ`. Human visual approval is
pending. Analytics remains blocked, real 3D speed is unavailable, and Stage 5C/6 have
not started. GPU calls, cloud calls, and spend were zero.
