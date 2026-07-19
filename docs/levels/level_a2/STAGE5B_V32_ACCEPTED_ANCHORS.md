# Stage 5B v3.2 — accepted contact anchors

The CPU rerun consumed 314 real ball observations, VFR timestamps, five approved
static contact anchors v4, five bounce constraints, and conservative total anchor
uncertainty. Temporal player tracks were not used as positions or motion evidence.

The result is `STAGE5B_V32_REJECTED_BY_HUMAN_GATE`: all five anchors were consumed, nine flights
were reconstructed, median reprojection is 7.0635 px, p95 is 27.4726 px, maximum
contact residual is 8.3071 m, maximum bounce residual is 0.01782 m, and there are
zero negative-Z violations. The p95 and contact-residual gates fail. Analytics stays
blocked. The human gate rejected the event-to-segment contact constraint.
