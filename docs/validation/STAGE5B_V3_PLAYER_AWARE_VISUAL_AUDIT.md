# Stage 5B v3 player-aware visual audit

Human visual approval: **rejected** by ChatGPT visual audit.

The gate rejected v3 because far contacts were outside plausible court positions, the
top view clipped problematic coordinates, all nine flights remained ambiguous, and
reprojection residuals were 25.2663 px median / 68.6564 px p95. Contact residuals near
machine zero were tautological ball-ray constraints, not independent validation. V3
did not optimize against all observations or execute real sensitivity perturbations;
homography, racket extension, robust loss, and other configuration fields did not all
affect the solution. Several visuals also joined segments or overlaid different times.

The five JPG previews provide reprojection metrics over a canonical source frame, a
metric top-view audit, a side-view height audit, five player/contact panels, and a
comparison of competing depth hypotheses. Top and side previews are diagnostics only;
they do not start or complete Stage 5C or Stage 6.

Review for implausible depth, contact reach, height, court-side identity, bounce Z=0,
trajectory discontinuity, and divergence between hypotheses. All nine flight segments
are explicitly ambiguous. This evidence does not authorize Analytics or real 3D speed.

GPU calls: 0. Cloud calls: 0. Spend: 0.
