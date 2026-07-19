# Stage 5B v3.1 metric correction report

Status: `STAGE5B_V31_REJECTED_BY_HUMAN_GATE`.

`human_visual_approval: rejected`: contacts were not physically plausible;
ev_003/ev_007 were 8.025/6.888 m behind the far baseline; optimized p95 27.106 px
exceeded 24 px. Homography was audit-only, ambiguity used initial Z instead of full
trajectories, near-equivalent costs hid incompatible flights, and the top view retained
doubtful play-space exits.

V3 was rejected by the ChatGPT visual gate. V3.1 renames the tautological ball-ray
residual, lifts both wrist rays into candidate 3D points, uses racket extension in
feasibility, audits homography/player coordinates, performs segment-specific seeded
multi-start, and fits `scipy.optimize.least_squares(loss="soft_l1")` against all 314
real VFR observations.

Median/p95 reprojection improved from 25.2663/68.6564 px to 6.7430/27.1056 px, a
73.31% median improvement. Nine flights were reconstructed; independent starts
converged without incompatible-depth alternatives, yielding nine resolved and zero
ambiguous segments. Maximum bounce residual is 0.0178 m, negative Z is zero, and 314
samples validate. Nine sensitivity reruns were executed.

Canonical XYZ checksum: `acd75021f827211fc4dfb99b7e33af80e3564af0c3af654940ae022ae6d34483`.

READY is not declared: p95 remains above the 24 px gate and the far P1 coordinates are
physically implausible because homography extrapolation places them 6.9–8.0 m behind
the far baseline. Human approval remains pending. Analytics, real speed, Stage 5C, and
Stage 6 remain blocked. GPU/cloud/spend: 0/0/0.
