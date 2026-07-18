# Stage 5B kinematics contract

Status: **PROPOSED_FOR_INTEGRATION_REVIEW**

An approved future producer should provide `frame_id`, `timestamp_seconds`, `x_m`, `y_m`, `z_m`,
`confidence`, `observed_or_interpolated`, `segment_id`, and `event_context`. Timestamps must be VFR
source timestamps and coordinates must share the documented court frame and metre unit.

Analytics will consume this read-only and retain interpolation status and uncertainty. This proposal
does not reopen, implement, or validate Stage 5B; until its human gate passes, 3D speed is unavailable.
