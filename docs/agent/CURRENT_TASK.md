# Current task

Core Stage 1A — Single Rally Contract & Existing-Output Import: synthetic gate
passed.

The read-only importer converts supplied existing events, ball observations and
2D court calibration into one versioned rally record and an Analysis Bundle V1.
It does not run inference, tracking, segmentation, models or Web code. The local
release is a synthetic contract fixture because `REAL_REFERENCE_VIDEO_MISSING` and
`REAL_STAGE3_BALL_TRACK_MISSING` remain blocked. Court semantics now explicitly
separate image pixels from court meters, and synthetic calibration is never
reported as approved.

The importer and contracts were accepted against the synthetic fixture only. No
real bundle exists; detailed record schemas remain candidates until tested with
real reference assets.
