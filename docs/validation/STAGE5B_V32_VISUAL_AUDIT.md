# Stage 5B v3.2 visual audit

`human_stage5b_v32_approval: rejected`

Gate: `STAGE5B_V32_REJECTED_BY_HUMAN_GATE`.
Failure class: `EVENT_TO_SEGMENT_CONTACT_CONSTRAINT_FAILED`.

Review the seven published images for real-frame observed/reprojected alignment,
separate flights, complete court and backcourt, five anchors with total CI95, bounce
placement, clipping, and hypothesis differences. Automated execution found no
negative Z and no rejected observations, but p95 reprojection (27.4726 px) and maximum
contact residual (8.3071 m) exceed their initial gates. This is evidence for human
evaluation, not Stage 5B approval.

The 8.307053579282034 m maximum contact residual exceeds the 2.5 m gate; several
trajectories visibly miss their anchors. P95 is 27.4726 px and maximum reprojection
is 54.522 px, while the prior sheet omitted the worst frames. Similar optimizer costs
do not establish physical validity, and a smooth ballistic curve cannot replace
compatible contact and bounce endpoints.
