# Stage 5B v3.1 visual audit

Human visual approval: **rejected**.

Six previews expose the full coordinate range, independent flight panels, per-frame
observed/reprojected pixels, player/baseline coordinate discrepancies, contact reach
and racket distance, and per-segment optimizer hypotheses. No segment boundary is
joined artificially and no out-of-zone player is clipped.

The human-gate status is `STAGE5B_V31_REJECTED_BY_HUMAN_GATE`. Contacts are not
physically plausible; ev_003 and ev_007 are respectively 8.025 m and 6.888 m behind
the far baseline; optimized p95 is 27.106 px (>24 px). The homography was audit-only,
the ambiguity metric compared only initial Z, near-equivalent costs concealed
materially different trajectories, and the top view retained doubtful flights.
Analytics and real 3D speed remain blocked.
