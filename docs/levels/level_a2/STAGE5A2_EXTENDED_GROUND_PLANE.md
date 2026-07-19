# Stage 5A.2 — Extended Ground-Plane Calibration

Status: `STAGE5A2_REJECTED_BY_HUMAN_GATE_EVIDENCE_INSUFFICIENT`.

Human visual approval is rejected. The previous evidence clipped far events, mislabeled
model-line evaluation as detection, offered no metric improvement or independent camera
validation, underestimated uncertainty, processed only five frames without temporal
support, used a median background for feet, and imposed an unjustified 5 m heuristic.

The CPU-only run sampled 31 distributed frames from the canonical A2 video, built a
temporal-median background, detected a white-line mask and distance transform, and
refined the Stage 1 homography with ten regulation lines plus the eight accepted
correspondences as a robust prior. Stage 1 and Stage 5A/5A.1 files remain unchanged.

Line distance median/p95 is 0.000/6.559 px before and after refinement. This automatic
mask metric passes its initial gate but the homography is effectively unchanged and
its condition is 39103.97. Camera/homography player-ground disagreement is small
(median 0.022 m), showing that both models agree with one another rather than provide
an independent correction of the off-court localization.

Five accepted P1 contact frames were processed using ankles, heels, toes, visibility,
confidence and bbox fallback policy. All are finite and identity-stable. Nevertheless,
ev_003 remains 7.938 m and ev_007 6.358 m behind the far baseline, beyond the documented
5 m plausibility region. The human observation that ev_003 appears roughly 2–3 m behind
the baseline is evaluation only and was not used by the optimizer.

The 64-run deterministic corner/line bootstrap reports uncertainty. Requested vertical,
resolution and camera-initial perturbations could not be executed independently because
their raw per-frame observations are not serialized; this limitation is explicit in
the uncertainty JSON. No XYZ reconstruction was run.

The next Stage 5B producer contract names the extended homography, extended camera and
player-ground JSONL. Its integration test proves calibration changes player anchors,
contact priors and the objective residual, rather than only an audit report.
