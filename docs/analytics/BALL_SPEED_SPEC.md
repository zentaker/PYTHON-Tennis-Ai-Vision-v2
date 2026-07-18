# Ball speed specification

All estimators use actual VFR `timestamp_seconds`, require strictly increasing finite timestamps,
reject non-positive `dt`, exclude configurable gaps, and robustly filter segment-speed outliers.
They return `unavailable` when evidence is insufficient.

- `pixel_apparent` reports pixels/second for diagnostics only.
- `court_planar_xy` reports planar metres/second and km/h. It ignores Z and must never be presented
  as real 3D ball speed.
- `estimated_3d` uses X/Y/Z metres and is the intended final sports measure, but depends on an
  approved Stage 5B contract. No Z is synthesized.

The contract reserves incoming/outgoing, peak outgoing, net, and pre/post-bounce metrics. A metric
remains null unless its event window and evidence exist. A two-sample result is warned; a larger
window is preferred. Values produced from synthetic tests validate mathematics, not real footage.

Contact-centered results expose independent `incoming_status` and `outgoing_status`. Global status is
`available` when both windows are available, `partial` when exactly one is available, and
`unavailable` when neither is available. The simple estimator represents its one computed result as
an available outgoing side. Its unit is explicit and constrained by the selected method.
