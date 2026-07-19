# ADR — Stage 5B v3 player-aware XYZ

Decision: Stage 5B v3 uses player-aware constraints and reports uncertainty; it does
not select arbitrary monocular depth as truth.

V1 and v2 were rejected at the human gate because mathematically low-cost trajectories
still produced implausible event geometry, depth, and visual motion. A fixed monocular
camera maps a 3D point to a pixel ray, leaving depth underdetermined away from Z=0.
Homography alone resolves only the court plane.

Accepted P1 evidence adds independent structure. A player's foot-derived court position
approximately fixes the body on court, while the 133-keypoint pose, both wrist pixels,
ball pixel, and accepted identity bound a plausible contact volume. The racket means the
ball must not be forced onto a wrist. Global height and reach limits, including a
configurable racket extension, are applied identically to every event. Both wrists are
evaluated because hitting hand is unknown. Bounce events independently fix Z=0, and
VFR-timed flight segments supply continuity and a configurable gravity prior.

The reconstruction evaluates multiple deterministic contact-depth hypotheses. Sample
confidence combines observation confidence and reprojection residual; uncertainty is
bounded by camera/contact uncertainty and spread between hypotheses. Similar-quality
solutions with incompatible depths remain `AMBIGUOUS`, with reduced confidence and
warnings. Hits may change velocity and bounces need not preserve vertical velocity.

This candidate requires a human visual gate because monocular ambiguity remains even
after player constraints. Analytics must not consume the XYZ, and no real 3D speed may
be published, until an explicit `APPROVED_STAGE5B_XYZ` decision exists.
