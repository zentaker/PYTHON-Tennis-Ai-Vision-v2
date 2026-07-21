# Stage 1B — Real Single Rally Bundle Candidate

This candidate documents a read-only import of existing local reference assets.
It is evidence for audit, not a human acceptance decision and not a new
inference run.

## Aligned references

- Selected external video: `nivel_a2_01/source.mp4` (10.488333 seconds,
  encoded 1536×2746 pixels, 527 frames).
- Canonical analysis space is 2746×1536 pixels after the recorded 90-degree
  display-matrix transform; track and court coordinates use this canonical space.
- Existing Stage 3 trajectory: `nivel_a2_01/smoothed_trajectory.csv`, with
  527 frame rows: 383 visible, 19 interpolated and 125 missing/non-visible.
- Existing VFR timestamps cover frames 0–526; Stage 4 manual events cover the
  same rally; existing 2D calibration is approved and non-synthetic.
- No source video, model, or personal filesystem path is copied into the
  versioned fixture.

## Candidate contents

The deterministic derived fixture contains one rally, 527 ball observations,
and 10 events: 4 contacts, 5 bounces and 1 serve. No out or unknown event is
introduced. The source surface is not declared by the available metadata, so it
remains `unknown`. `manifest.status` is `complete`; `session.status` and
`rallies.status` are `partial` because the source track preserves non-visible
observations rather than fabricating positions.

The bundle uses canonical image-pixel observations and an existing 2D
pixel-to-court calibration with `calibration_status: approved` and
`court_layout: doubles`; it makes no 3D or Stage 5B claim. Two independent builds
have the same fingerprint and source verification passes. SVG previews are
segmented at missing observations and show the track/court and event timeline
without embedding video frames.

## Gate

`REAL_REFERENCE_ASSET_ALIGNMENT_PASSED` is derived from 22 explicit checks.
`STAGE1B_REAL_EVIDENCE_AUDIT_PASSED` and `REAL_SINGLE_RALLY_DATA_GATE_PASSED`
are recorded. Fixture publication is restricted and atomic under
`STAGE1B_FIXTURE_PUBLICATION_SAFETY_PATCH_IMPLEMENTED`. The merge gate remains
`REAL_SINGLE_RALLY_MERGE_GATE_PENDING_FINAL_RELEASE_AUDIT`. Human review of the
release evidence is the next gate; this document must not be read as approval.
