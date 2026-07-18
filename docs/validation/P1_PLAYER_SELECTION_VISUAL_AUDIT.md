# P1 Player Selection and Visual Audit

Status: `P1_PLAYER_SELECTION_READY_FOR_GPU_RETEST`

The deterministic post-detection selector analyzed the ten recovered RTX 3090 smoke frames without cloud or GPU calls. It evaluates foot-anchor distance to the doubles-court rectangle, a bounded lateral and baseline margin, bbox plausibility by court side, detector and foot confidence, temporal presence, spatial/track continuity, and contact compatibility. Invalid geometry is rejected before ranking, so an absent player is never filled with a spectator.

From 58 original person detections, the selector retained one near and one far player in every frame and rejected 38 candidates. All selected poses preserve 133 keypoints and include wrists, ankles, heels, and toe points. No identity-switch flags were produced. Five contact records were rebuilt against the selected track, pose, court position, bbox, foot anchor, and nearest wrist distance.

Per-frame automated gates report 10 PASS, 0 PARTIAL, and 0 FAIL. The compact contact sheet and ten selected/diagnostic overlays are stored under the ignored local artifact directory `.artifacts/p1-runpod-3090-smoke/player-selection/`, alongside the six machine-readable selected outputs. The geometry is suitable for a new GPU retest, but the current images are not declared human-approved and the full rally remains unvalidated.

The reusable baseline allowance is 8.5 m behind a baseline and the lateral allowance is 1.5 m beyond the doubles sideline. These are global court-relative parameters, not frame-specific or track-specific coordinates.
