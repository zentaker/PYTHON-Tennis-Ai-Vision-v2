# Stage 5A.2C contact ground visual audit

Reviewer: ChatGPT artifact visual and implementation audit.

- `contact_ground_anchor_human_gate: CONTACT_GROUND_ANCHORS_VISUAL_AND_GEOMETRIC_GATE_PASSED`
- `temporal_player_motion_gate: TEMPORAL_PLAYER_MOTION_VALIDATION_PARTIAL`
- Approved anchors: ev_001, ev_003, ev_005, ev_007, ev_009.

Seven previews show actual fitted line families, five real contact frames, adjacent
valid/invalid tracking sequences, rejected transitions, auto-expanded contact anchors,
far-contact evidence and executed uncertainty sources. No person validation uses the
median background; no far point is clipped or forced toward the court.

The five static contact anchors are approved: foot pixels are on the players, identities
are correct, no switch/clipping is visible, and 6–8 m far positions are plausible.
Temporal motion remains partial and must not feed movement metrics. ev_007 is an accepted
6.632 m far observation. ev_003 remains unresolved because its local valid-speed p95 is
13.021 m/s (>12), but that warning no longer invalidates its approved static anchor.
