# Stage 5B v3.1 coordinate audit

The court convention is verified: X right, Y toward far court, Z up, net Y=0,
baselines ±11.885 m, singles width 8.23 m, and doubles width 10.97 m.

P1 stored player XY matches direct Stage 1 homography recomputation from foot pixels to
within `1.78e-15 m`; there is no serialization drift. `ev_001` is 1.128 m inside the
near baseline. `ev_003` is 8.025 m behind the far baseline, not the expected human
reference of roughly 2–3 m. `ev_007` is similarly 6.888 m behind. The cause is unstable
planar homography extrapolation beyond the calibrated court, and v3.1 does not silently
move or clamp those players. Both far contacts remain a blocker.
