# Confidence and uncertainty

Confidence is an auditable set of components, never one opaque score:
`event_timing_confidence`, `player_identity_confidence`, `contact_confidence`,
`trajectory_confidence`, `speed_confidence`, `stroke_side_confidence`,
`contact_mode_confidence`, `spin_family_confidence`, and `tactical_shape_confidence`.

Each component records source, method, a value in [0,1], warnings, dependencies, and whether the
evidence is human-labeled, model-inferred, or geometry-derived. Zero means unavailable rather than
evidence that an event did not happen. Consumers must inspect dependencies and warnings.
