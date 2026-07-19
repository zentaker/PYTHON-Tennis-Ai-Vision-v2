# Stage 5B v3.3 — event topology and endpoint feasibility

The canonical ten-event timeline produces nine non-overlapping flights containing
exactly 314 valid observations. Event mapping, endpoint side, timestamps, frames, and
bounce constraints pass. Player foot anchors are descriptive ground positions, not
ball-impact points; v3.3 builds contact volumes from total CI95, P1 pose/wrists,
body reach, racket extension, ball pixels, and height uncertainty.

Phase A failed because 0/5 v3.2 endpoints are within 0.50 m of their feasible contact
volumes. Maximum excess is 3.86798 m, while all 5/5 bounce constraints pass. Per the
two-phase contract, the 314-observation Phase B optimization was not executed. Global
status is `STAGE5B_V33_ENDPOINT_FEASIBILITY_FAILED`; Analytics and XYZ remain blocked.
