# Stroke taxonomy v1

Analytics v1 is separate from the historical Stage 4 `shot_type`; it does not replace or
rewrite that label. A stroke is described independently by `stroke_side`, `contact_mode`,
`spin_family`, `tactical_shape`, and `hitting_hand`, using the values in
`config/analytics/stroke_taxonomy_v1.json`.

Every dimension permits `unknown` and carries its own source, method, confidence, warnings,
dependencies, and evidence flags. Missing evidence is never filled from another dimension. A
drop may be slice, a lob may be topspin, and a forehand may be flat, topspin, or slice.

Human ground truth must be explicitly declared. Otherwise labels remain human observation,
geometry-derived evidence, model inference, or an unvalidated hypothesis as applicable.
