# Stage 5A.2B — Temporal Player Ground Validation

Stage 5A.2B uses real event frames and CPU-only pyramidal Lucas–Kanade tracking around
each accepted P1 contact. It performs no neural inference and does not execute Stage 5B
XYZ. The five temporal windows use radius ±30 frames and preserve near/far identities.

Court evidence is now named precisely: LSD image segments are detected inside a
conservative visible-ground polygon, then associated with painted model lines by image
distance and orientation. The net is excluded from the painted-ground model. Geometry
families are cross-validated and explicitly marked `correlated_geometry_sources: true`;
camera and homography are not treated as independent measurements.

The 5 m backcourt heuristic is removed. Far observations are accepted only when real
foot pixels, ground region, temporal continuity, calibration-family spread and distance
from the projective singularity are stable. Physically impossible speed diagnostics
indicate optical-flow drift and force `unresolved`; they are not player-speed product
metrics.

Contact-frame visual gate: `CONTACT_FRAME_FOOT_VISUAL_GATE_PASSED` for all five events.
Temporal gate: `STAGE5A2B_TEMPORAL_VALIDATION_REJECTED`; global status
`STAGE5A2B_REJECTED_BY_HUMAN_GATE_TRACKER_INVALID`. The 143.144 m/s diagnostic is
tracker drift, not movement. XYZ/Analytics/Stage 5C/Stage 6 remain blocked.
