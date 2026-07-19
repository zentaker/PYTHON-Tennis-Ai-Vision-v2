# Stage 5B v3.5 / v3.5.1 measurement-integrity and observation-conditioned audit

## V3.5.1 reviewer rejection and truthful rerun

The V3.5 implementation was rejected by the ChatGPT implementation and artifact
audit because Gate D was unconditional, anomalies were not weighted, fixed V3.4
nodes were reused, the drag model was an alias, and residual/visual evidence was
incomplete. V3.5.1 records that rejection in
`config/stage5b_v3/stage5b_v35_result.json`.

The V3.5.1 rerun applies per-observation usability, weights and sigma values,
generates candidates from every declared event frame, performs candidate-based
weighted edge search, retains alternatives, writes one residual row per accounted
observation, and publishes real frame-indexed evidence. Gate B remains unexecuted
and no XYZ output is produced.

`human_stage5b_v35_approval: pending`

Gate D passed with all 314 observations inventoried. Forty-nine duplicate/frozen
coordinates and 13 kinematically suspicious observations are reported, not removed.
Raw, smoothed and P1 sources share one correlated Stage 3 provenance group.

Gate A is `STAGE5B_V35_OBSERVATION_CONDITIONED_NODES_PARTIAL`: edge costs include
interior observations, robust reprojection, holdout splits, timing and physical terms,
but coarse median/p95 reprojection are 29.29/68.30 px. Gate B was not executed and no
XYZ was fabricated. Flights 03, 05, 07 and 09 are explicitly audited.
