# Stage 5A.2C — Contact Ground Anchors

Status: `STAGE5A2C_CONTACT_GROUND_ANCHORS_PARTIAL`.

Sixty-one accepted real LSD segments now participate directly in robust homography
fitting. Fifteen identifiable calibration families use genuine longitudinal/transverse,
leave-one-family-out and deterministic segment subsets. Ensemble line median/p95 is
2.484/6.414 px. Radial distortion is explicitly not identifiable and is not represented
as a calculation.

The tracker propagates only across adjacent real frames in forward/backward chains,
updating features, bbox and foot through a RANSAC affine transform. Invalid transitions
are rejected and excluded from PTS-based speed. The contact-local ±5 gate accepts
ev_001, ev_005 and ev_007. ev_003 and ev_009 remain unresolved because local p95 speed
exceeds 12 m/s; distant failures do not invalidate otherwise stable contacts.

Five contact anchors were produced. ev_003 remains 7.721 m and ev_007 6.632 m behind
the far baseline without a distance cap. XYZ was not executed; downstream stages remain
blocked pending human audit.
