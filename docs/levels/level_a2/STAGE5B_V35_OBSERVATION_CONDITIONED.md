# Stage 5B v3.5 observation-conditioned bundle

Measurement Gate D passed: 314 observations, complete provenance, declared event
ranges, and explicit anomaly classifications. Gate A scores each candidate edge using
all interior observations and holdout metrics rather than speed alone. The coarse
Gate A result is partial (median/p95 29.29/68.30 px), so Gate B is intentionally not
executed. The global state is `STAGE5B_V35_MEASUREMENT_LIMITED`; Analytics remains
blocked and human approval is pending.

V3.5.1 records the prior implementation rejection and reruns the measurement gate
truthfully: anomaly weights are applied, declared event frames generate candidates,
V3.4 selected nodes are not reused, alternatives and residual rows are retained,
and real frame-indexed evidence is published. Gate B remains blocked.
